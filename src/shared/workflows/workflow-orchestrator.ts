import { access } from "node:fs/promises";
import type { ConfirmChannel } from "amqplib";

import { env } from "../config/env.js";
import { JobsRepository } from "../db/jobs-repository.js";
import {
  ArtifactsRepository,
  RequirementsRepository,
  WorkflowRunsRepository,
  WorkflowStepsRepository,
} from "../db/workflow-repository.js";
import { withTransaction } from "../db/postgres.js";
import { buildSkillJobMessage, type JobRecord } from "../jobs/job-types.js";
import { getErrorMessage } from "../logging/logger.js";
import { publishJson } from "../rabbitmq/rabbitmq.js";
import type { WorkflowStepRecord } from "./workflow-types.js";

/**
 * Helper minimo para validar si un artifact fisico ya existe en disco.
 *
 * El orquestador lo usa despues de que el worker termina un job para no
 * confiar solo en el exit code del proceso: ademas del "salio bien",
 * verificamos que los archivos esperados realmente quedaron persistidos.
 */
async function fileExists(path: string) {
  try {
    await access(path);
    return true;
  } catch {
    return false;
  }
}

/**
 * Convierte la metadata declarativa del step en una lista concreta de
 * artifacts esperados para esa ejecucion.
 *
 * Fuente:
 * - `producedArtifactTypes`: tipos logicos del step, por ejemplo
 *   `design_handoff` o `quote_output`
 * - `stepPayload.expectedArtifacts`: rutas absolutas que se calcularon al
 *   lanzar el workflow
 *
 * La posicion en ambos arrays se usa como contrato simple:
 * - indice 0 del tipo <-> indice 0 de la ruta
 * - indice 1 del tipo <-> indice 1 de la ruta
 */
function getExpectedArtifacts(step: WorkflowStepRecord) {
  const paths = Array.isArray(step.stepPayload.expectedArtifacts)
    ? step.stepPayload.expectedArtifacts.filter(
      (value): value is string => typeof value === "string" && value.trim().length > 0,
    )
    : [];

  return step.producedArtifactTypes.map((artifactType, index) => ({
    artifactType,
    absolutePath: paths[index] ?? null,
  }));
}

/**
 * Decide si un step pendiente ya puede convertirse en siguiente trabajo
 * ejecutable.
 *
 * Reglas:
 * - el step todavia debe estar en `PENDING`
 * - todos sus `dependsOnSteps` deben estar completos
 * - todos sus `requiredArtifactTypes` deben existir ya en el workflow
 *
 * Este helper es la pieza que aterriza la idea de:
 * "RabbitMQ es async, pero el workflow sigue siendo secuencial cuando
 * depende de artifacts previos".
 */
function isStepUnlocked(
  step: WorkflowStepRecord,
  completedStepNames: Set<string>,
  availableArtifactTypes: Set<string>,
) {
  if (step.status !== "PENDING") {
    return false;
  }

  return (
    step.dependsOnSteps.every((dependency) => completedStepNames.has(dependency)) &&
    step.requiredArtifactTypes.every((artifactType) => availableArtifactTypes.has(artifactType))
  );
}

/**
 * Orquestador de continuidad del workflow.
 *
 * Responsabilidad principal:
 * - reaccionar cuando un job ya arranco o ya termino
 * - mantener sincronizados los estados de `workflow_step`, `workflow_run`
 *   y `requirement`
 * - registrar artifacts producidos por cada step
 * - decidir si corresponde crear y encolar el siguiente job
 *
 * En otras palabras:
 * - `workflow-launch-service` "siembra" el workflow y crea el primer job
 * - `workflow-orchestrator` continua el workflow step por step
 */
export class WorkflowOrchestratorService {
  /**
   * Recibe los repositorios del dominio y el canal publicador de RabbitMQ.
   *
   * El orquestador no ejecuta procesos por si mismo; usa estos colaboradores
   * para:
   * - leer/escribir estado en base de datos
   * - crear nuevos jobs
   * - publicarlos en la misma cola de skills
   */
  constructor(
    private readonly requirementsRepository: RequirementsRepository,
    private readonly workflowRunsRepository: WorkflowRunsRepository,
    private readonly workflowStepsRepository: WorkflowStepsRepository,
    private readonly artifactsRepository: ArtifactsRepository,
    private readonly jobsRepository: JobsRepository,
    private readonly publisherChannel: ConfirmChannel,
  ) { }

  /**
   * Marca el inicio formal del step dentro del dominio del workflow.
   *
   * El worker ya habia movido el job a `RUNNING` en la tabla `jobs`.
   * Este metodo completa la foto del dominio actualizando:
   * - `workflow_steps.status = RUNNING`
   * - `workflow_runs.status = RUNNING`
   * - `workflow_runs.current_step_name = <step actual>`
   *
   * Si el job no pertenece a un workflow, no hace nada.
   */
  async handleJobStarted(job: JobRecord) {
    if (!job.workflowStepId || !job.workflowRunId) {
      return;
    }

    await withTransaction(async (client) => {
      // Sincroniza el estado del step con el estado operativo del job.
      await this.workflowStepsRepository.markRunning(job.workflowStepId!, job.id, client);

      // Relee el step para obtener su nombre logico y reflejarlo en el
      // workflow_run como "paso actual".
      const step = await this.workflowStepsRepository.findById(job.workflowStepId!, client);
      if (step) {
        await this.workflowRunsRepository.markRunning(job.workflowRunId!, step.stepName, client);
      }
    });
  }

  /**
   * Reconciliador principal que corre cuando un job ya termino.
   *
   * Casos que cubre:
   * - si el job fallo: cierra step/workflow/requirement en `FAILED`
   * - si el job termino bien:
   *   1. registra los artifacts fisicos
   *   2. marca el step en `COMPLETED`
   *   3. evalua si el workflow ya termino
   *   4. si no termino, revisa que steps siguientes quedaron desbloqueados
   *   5. crea los nuevos jobs necesarios
   *   6. fuera de la transaccion, los publica en RabbitMQ
   *
   * La publicacion se hace fuera de la transaccion para no dejar abierta
   * una TX de PostgreSQL mientras esperamos confirmacion del broker.
   */
  async reconcileAfterJob(job: JobRecord) {
    if (!job.workflowStepId || !job.workflowRunId || !job.requirementUuid || !job.caseRootDir) {
      return;
    }

    let jobsToPublish: Array<{ job: JobRecord; stepName: string; workflowStepId: string }> = [];
    try {
      jobsToPublish = await withTransaction(async (client) => {
        // Carga el contexto completo del job para no depender solo del mensaje
        // de cola o del payload del step.
        const workflowStep = await this.workflowStepsRepository.findById(job.workflowStepId!, client);
        const workflowRun = await this.workflowRunsRepository.findById(job.workflowRunId!, client);
        const requirement = await this.requirementsRepository.findById(job.requirementUuid!, client);

        if (!workflowStep || !workflowRun || !requirement) {
          throw new Error(`Workflow context not found while reconciling job ${job.id}.`);
        }

        if (job.status === "FAILED") {
          // Si el proceso ya acabo en error, no intentamos continuar el flujo.
          // Cerramos el step, el workflow y el requirement como fallidos.
          const errorMessage = job.errorMessage ?? "Workflow step failed.";
          await this.workflowStepsRepository.markFailed(workflowStep.id, errorMessage, job.id, client);
          await this.workflowRunsRepository.markFailed(workflowRun.id, errorMessage, client);
          await this.requirementsRepository.markStatus(requirement.id, "FAILED", client);
          return [];
        }

        // Si el proceso termino bien, validamos y registramos primero sus
        // artifacts esperados antes de dar por completado el step.
        await this.registerArtifactsForStep(job, workflowStep, requirement.rootDir, client);
        await this.workflowStepsRepository.markCompleted(workflowStep.id, job.id, client);

        // Relee todo el estado del workflow ya con el step actualizado para
        // decidir si el flujo termino o si se desbloquean pasos siguientes.
        const steps = await this.workflowStepsRepository.listByWorkflowRunId(workflowRun.id, client);
        const completedStepNames = new Set(
          steps.filter((step) => step.status === "COMPLETED").map((step) => step.stepName),
        );
        const artifacts = await this.artifactsRepository.listByWorkflowRunId(workflowRun.id, client);
        const availableArtifactTypes = new Set(artifacts.map((artifact) => artifact.artifactType));

        if (steps.every((step) => step.status === "COMPLETED")) {
          // Si todos los steps ya estan completos, cerramos el flujo y el caso.
          await this.workflowRunsRepository.markCompleted(workflowRun.id, client);
          await this.requirementsRepository.markStatus(requirement.id, "COMPLETED", client);
          return [];
        }

        // Busca solo los steps aun pendientes que ya cumplen dependencias
        // logicas y disponibilidad de artifacts.
        const unlockedSteps = steps.filter((step) =>
          isStepUnlocked(step, completedStepNames, availableArtifactTypes),
        );

        const nextJobs: Array<{ job: JobRecord; stepName: string; workflowStepId: string }> = [];
        for (const step of unlockedSteps) {
          // Crea el siguiente job operativo, ya asociado al mismo requirement
          // y workflow_run, para mantener trazabilidad del caso completo.
          const nextJob = await this.jobsRepository.createPendingJob(
            {
              skillName: step.skillName,
              payload: step.stepPayload,
              notificationEmail: requirement.notifyEmail,
              requirementCode: requirement.requirementCode,
              requirementUuid: requirement.id,
              executionMode: workflowRun.executionMode,
              workflowName: workflowRun.workflowName,
              stepName: step.stepName,
              workflowRunId: workflowRun.id,
              workflowStepId: step.id,
              caseRootDir: requirement.rootDir,
              ...(typeof step.stepPayload.outputDir === "string"
                ? { outputDir: step.stepPayload.outputDir }
                : {})
              /*  outputDir:
                 typeof step.stepPayload.outputDir === "string"
                   ? step.stepPayload.outputDir
                   : undefined, */
            },
            client,
          );

          // Lo deja en READY a nivel de step mientras aun no se ha publicado.
          await this.workflowStepsRepository.markReady(step.id, nextJob.id, client);
          nextJobs.push({
            job: nextJob,
            stepName: step.stepName,
            workflowStepId: step.id,
          });
        }

        return nextJobs;
      });
    } catch (error) {
      // Si algo falla durante la reconciliacion, degradamos el workflow a
      // FAILED para no dejarlo en un estado ambiguo o parcialmente avanzado.
      const message = `Workflow reconciliation failed for job ${job.id}: ${getErrorMessage(error)}`;
      await this.failWorkflowFromJobContext(job, message);
      throw error;
    }

    // Publica los nuevos jobs solo despues de cerrar la transaccion.
    for (const next of jobsToPublish) {
      await this.publishPreparedJob(job, next.job, next.workflowStepId, next.stepName);
    }
  }

  /**
   * Fallback defensivo para cerrar el workflow como fallido a partir del
   * contexto minimo del job actual.
   *
   * Se usa cuando algo falla durante la reconciliacion misma, por ejemplo:
   * - falta un artifact esperado
   * - no se encontro el contexto completo del workflow
   * - ocurrio un error inesperado al preparar el siguiente step
   */
  private async failWorkflowFromJobContext(job: JobRecord, message: string) {
    if (!job.workflowStepId || !job.workflowRunId || !job.requirementUuid) {
      return;
    }

    await withTransaction(async (client) => {
      // Propaga el fallo a todos los niveles de estado del dominio.
      await this.workflowStepsRepository.markFailed(job.workflowStepId!, message, job.id, client);
      await this.workflowRunsRepository.markFailed(job.workflowRunId!, message, client);
      await this.requirementsRepository.markStatus(job.requirementUuid!, "FAILED", client);
    });
  }

  /**
   * Registra en DB los artifacts que el step debia producir.
   *
   * Validaciones clave:
   * - cada artifact esperado debe tener ruta configurada
   * - cada ruta debe existir fisicamente en disco
   *
   * Solo despues de eso hacemos `upsert` en la tabla `artifacts`.
   * Asi evitamos declarar completo un step que no dejo realmente sus archivos.
   */
  private async registerArtifactsForStep(
    job: JobRecord,
    step: WorkflowStepRecord,
    rootDir: string,
    executor: Parameters<ArtifactsRepository["upsertByAbsolutePath"]>[1],
  ) {
    const expectedArtifacts = getExpectedArtifacts(step);

    if (expectedArtifacts.length === 0) {
      return;
    }

    for (const artifact of expectedArtifacts) {
      if (!artifact.absolutePath) {
        throw new Error(
          `Workflow step "${step.stepName}" is missing the expected artifact path for "${artifact.artifactType}".`,
        );
      }

      const exists = await fileExists(artifact.absolutePath);
      if (!exists) {
        throw new Error(
          `Expected artifact "${artifact.artifactType}" was not generated at ${artifact.absolutePath}.`,
        );
      }

      // Persiste el artifact ligado al mismo requirement/workflow/step/job.
      await this.artifactsRepository.upsertByAbsolutePath(
        {
          requirementId: job.requirementUuid!,
          workflowRunId: job.workflowRunId,
          workflowStepId: step.id,
          jobId: job.id,
          rootDir,
          artifactType: artifact.artifactType,
          absolutePath: artifact.absolutePath,
          metadata: {
            stepName: step.stepName,
            jobId: job.id,
          },
        },
        executor,
      );
    }
  }

  /**
   * Publica en RabbitMQ un job que ya fue creado en DB durante la
   * reconciliacion.
   *
   * Si la publicacion funciona:
   * - el step pasa a `ENQUEUED`
   * - el workflow vuelve a reflejar el `current_step_name`
   *
   * Si la publicacion falla:
   * - se marca el job como `FAILED`
   * - se marca el step como `FAILED`
   * - se marca el workflow como `FAILED`
   * - se marca el requirement como `FAILED`
   */
  private async publishPreparedJob(
    sourceJob: JobRecord,
    nextJob: JobRecord,
    workflowStepId: string,
    stepName: string,
  ) {
    try {
      // Publica el nuevo job usando la misma cola general de skills.
      await publishJson(
        this.publisherChannel,
        env.skillJobsQueue,
        buildSkillJobMessage(nextJob),
      );

      await withTransaction(async (client) => {
        // Una vez el broker acepto el mensaje, el step ya puede reflejarse
        // como encolado y el workflow como nuevamente en curso.
        await this.workflowStepsRepository.markEnqueued(workflowStepId, nextJob.id, client);
        if (nextJob.workflowRunId) {
          await this.workflowRunsRepository.markRunning(nextJob.workflowRunId, stepName, client);
        }
      });
    } catch (error) {
      const message = `Unable to publish next workflow job ${nextJob.id}: ${getErrorMessage(error)}`;

      await withTransaction(async (client) => {
        // Si no pudimos encolar el siguiente trabajo, fallamos el flujo para
        // no dejar un "paso listo" sin execution real en RabbitMQ.
        await this.jobsRepository.markQueuePublishFailed(nextJob.id, message, client);
        await this.workflowStepsRepository.markFailed(workflowStepId, message, nextJob.id, client);

        if (nextJob.workflowRunId) {
          await this.workflowRunsRepository.markFailed(nextJob.workflowRunId, message, client);
        }

        if (sourceJob.requirementUuid) {
          await this.requirementsRepository.markStatus(sourceJob.requirementUuid, "FAILED", client);
        }
      });

      throw error;
    }
  }
}
