import type { ConfirmChannel } from "amqplib";
import { resolve } from "node:path";

import { env } from "../../../shared/config/env.js";
import { JobsRepository } from "../../../shared/db/jobs-repository.js";
import {
  RequirementsRepository,
  WorkflowRunsRepository,
  WorkflowStepsRepository,
} from "../../../shared/db/workflow-repository.js";
import { withTransaction } from "../../../shared/db/postgres.js";
import {
  buildSkillJobMessage,
  type CreateJobRequest,
  type JobPayload,
} from "../../../shared/jobs/job-types.js";
import { isRegisteredSkill, listAvailableSkills } from "../../../shared/jobs/skill-registry.js";
import {
  ensureRequirementWorkspace,
  ensureWorkflowStepWorkspace,
} from "../../../shared/requirements/requirement-context.js";
import {
  assertWorkflowSkillsRegistered,
  type WorkflowStepDefinition,
} from "../../../shared/workflows/workflow-definitions.js";
import type {
  CreateWorkflowRunRequest,
  WorkflowLaunchResult,
} from "../../../shared/workflows/workflow-types.js";
import { getErrorMessage } from "../../../shared/logging/logger.js";
import { publishJson } from "../../../shared/rabbitmq/rabbitmq.js";

export class QueuePublishError extends Error {
  /**
   * Error tecnico usado cuando el primer job del flujo ya fue persistido
   * pero no pudo publicarse en RabbitMQ.
   *
   * Esto permite distinguir:
   * - fallos de validacion o modelado del workflow
   * - fallos de infraestructura al intentar encolar
   */
  constructor(message: string) {
    super(message);
    this.name = "QueuePublishError";
  }
}

export class UnsupportedSkillError extends Error {
  /**
   * Error de negocio para frenar el flujo cuando una skill solicitada
   * no esta registrada en el worker actual.
   *
   * Se usa sobre todo en ejecuciones standalone, donde el usuario pide
   * una skill puntual y debemos validar temprano antes de crear registros
   * en DB o preparar carpetas.
   */
  constructor(skillName: string) {
    super(
      `Skill "${skillName}" is not registered. Available skills: ${listAvailableSkills().join(", ")}`,
    );
    this.name = "UnsupportedSkillError";
  }
}

/**
 * Devuelve el primer item de una lista o falla explicitamente si la lista
 * viene vacia.
 *
 * En este servicio la usamos para evitar asumir silenciosamente que siempre
 * existe un primer step. Eso hace que el flujo falle con un mensaje claro
 * si por algun bug se intenta lanzar un workflow sin pasos.
 */
function requireFirstItem<T>(items: T[], context: string) {
  const first = items[0];

  if (!first) {
    throw new Error(`Expected at least one item while ${context}.`);
  }

  return first;
}

/**
 * Intenta inferir un nombre amigable del caso (`case_name`) a partir del
 * payload recibido por API.
 *
 * Prioridad:
 * 1. `fallback`, si el request ya envio un nombre explicito.
 * 2. Campos frecuentes del payload como `site_name`, `client_name`
 *    o `project_name`.
 * 3. `null` si no hay nada usable.
 *
 * Este nombre solo ayuda a trazabilidad humana; el identificador real del
 * caso sigue siendo `requirement_code` generado por PostgreSQL.
 */
function inferCaseName(payload: JobPayload, fallback?: string) {
  if (fallback?.trim()) {
    return fallback.trim();
  }

  const candidateKeys = ["site_name", "client_name", "project_name"];
  for (const key of candidateKeys) {
    const value = payload[key];
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
  }

  return null;
}

function extractCaseDescription(payload: JobPayload) {
  const candidateKeys = [
    "prompt",
    "caseDescription",
    "case_description",
    "requirement",
    "description",
  ];

  for (const key of candidateKeys) {
    const value = payload[key];
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
  }

  return null;
}

function resolveWorkflowArtifactPaths(caseRootDir: string) {
  const designDir = resolve(caseRootDir, "design");
  const quoteDir = resolve(caseRootDir, "quote");
  const proposalDir = resolve(caseRootDir, "proposal");

  return {
    design: {
      outputDir: designDir,
      handoffPath: resolve(designDir, "network_design_handoff.json"),
      explanationPath: resolve(designDir, "network_design_explanation.md"),
      pdfPath: resolve(designDir, "network_design_explanation.pdf"),
    },
    quote: {
      outputDir: quoteDir,
      outputPath: resolve(quoteDir, "network_quote_output.json"),
      explanationPath: resolve(quoteDir, "network_quote_explanation.md"),
      pdfPath: resolve(quoteDir, "network_quote_explanation.pdf"),
    },
    proposal: {
      outputDir: proposalDir,
      contextPath: resolve(proposalDir, "proposal_network_context.json"),
      specPath: resolve(proposalDir, "proposal_network_spec.json"),
      presentationPath: resolve(proposalDir, "propuesta-economica-final.pptx"),
    },
  };
}

/**
 * Construye el payload operativo del primer y unico step cuando el request
 * entra por `POST /jobs` en modo standalone.
 *
 * La idea es traducir un payload de API orientado al usuario a un payload
 * ejecutable por el worker.
 *
 * Casos actuales:
 * - `diseno-redes-empresariales`: necesita `inputFile` y `outputDir`
 * - `cotizacion-redes-empresariales`: necesita `inputFile` y `outputDir`
 * - otras skills: se conserva el payload original
 *
 * El `requestSnapshotPath` apunta al JSON persistido dentro de la carpeta
 * del requirement, para que la ejecucion ya no dependa de rutas arbitrarias
 * externas.
 */
function buildStandaloneStepPayload(
  skillName: string,
  payload: JobPayload,
  requestSnapshotPath: string,
  caseRootDir: string,
  outputDir: string,
) {
  const artifacts = resolveWorkflowArtifactPaths(caseRootDir);

  if (skillName === "diseno-redes-empresariales") {
    const caseDescription = extractCaseDescription(payload);
    return {
      inputFile: requestSnapshotPath,
      caseRootDir,
      outputDir,
      ...(caseDescription ? { caseDescription } : {}),
      expectedArtifacts: [
        artifacts.design.handoffPath,
        artifacts.design.explanationPath,
        artifacts.design.pdfPath,
      ],
    };
  }

  if (skillName === "cotizacion-redes-empresariales") {
    return {
      inputFile: requestSnapshotPath,
      caseRootDir,
      outputDir,
      expectedArtifacts: [
        artifacts.quote.outputPath,
        artifacts.quote.explanationPath,
        artifacts.quote.pdfPath,
      ],
    };
  }

  if (skillName === "creacion-propuesta") {
    return {
      ...payload,
      caseRootDir,
      outputDir,
      finalPresentationPath:
        typeof payload.finalPresentationPath === "string" && payload.finalPresentationPath.trim()
          ? payload.finalPresentationPath
          : resolve(outputDir, "propuesta-economica-final.pptx"),
      expectedArtifacts: [
        artifacts.proposal.contextPath,
        artifacts.proposal.specPath,
        typeof payload.finalPresentationPath === "string" && payload.finalPresentationPath.trim()
          ? payload.finalPresentationPath
          : artifacts.proposal.presentationPath,
      ],
    };
  }

  return payload;
}

/**
 * Construye el payload operativo de cada step de un workflow orquestado.
 *
 * Este metodo toma la definicion logica del step (`design`, `quote`,
 * `proposal`) y la transforma al contrato que entiende la skill real.
 *
 * Cada payload queda amarrado al mismo `caseRootDir` y a rutas de artifacts
 * deterministicas dentro del requirement:
 * - `design`: consume el request snapshot inicial
 * - `quote`: consume el handoff de `design`
 * - `proposal`: consume `design_handoff` y `quote_output`
 *
 * Esto mantiene el desacople entre steps, pero evita que un step siguiente
 * tenga que resolver rutas manuales o inputs arbitrarios fuera del caso.
 */
function buildWorkflowStepPayload(
  step: WorkflowStepDefinition,
  requestSnapshotPath: string,
  caseRootDir: string,
  outputDir: string,
  requestPayload?: JobPayload,
) {
  const artifacts = resolveWorkflowArtifactPaths(caseRootDir);

  if (step.stepName === "design") {
    const caseDescription = requestPayload ? extractCaseDescription(requestPayload) : null;
    return {
      inputFile: requestSnapshotPath,
      caseRootDir,
      outputDir,
      ...(caseDescription ? { caseDescription } : {}),
      expectedArtifacts: [
        artifacts.design.handoffPath,
        artifacts.design.explanationPath,
        artifacts.design.pdfPath,
      ],
    };
  }

  if (step.stepName === "quote") {
    return {
      inputFile: artifacts.design.handoffPath,
      caseRootDir,
      outputDir,
      expectedArtifacts: [
        artifacts.quote.outputPath,
        artifacts.quote.explanationPath,
        artifacts.quote.pdfPath,
      ],
    };
  }

  return {
    designHandoffPath: artifacts.design.handoffPath,
    quoteOutputPath: artifacts.quote.outputPath,
    caseRootDir,
    outputDir,
    build: true,
    finalPresentationPath: artifacts.proposal.presentationPath,
    expectedArtifacts: [
      artifacts.proposal.contextPath,
      artifacts.proposal.specPath,
      artifacts.proposal.presentationPath,
    ],
  };
}

export class WorkflowLaunchService {
  /**
   * Servicio principal de arranque de ejecuciones.
   *
   * Responsabilidades:
   * - crear el requirement del caso
   * - crear el workflow_run
   * - crear los workflow_steps
   * - crear el primer job operativo
   * - publicar ese primer job a RabbitMQ
   *
   * No resuelve aun la reconciliacion completa del workflow despues de cada
   * step; este servicio solo cubre el "bootstrap" inicial del flujo.
   */
  constructor(
    private readonly requirementsRepository: RequirementsRepository,
    private readonly workflowRunsRepository: WorkflowRunsRepository,
    private readonly workflowStepsRepository: WorkflowStepsRepository,
    private readonly jobsRepository: JobsRepository,
    private readonly publisherChannel: ConfirmChannel,
  ) {}

  /**
   * Publica en RabbitMQ el primer job del workflow ya persistido en DB y
   * sincroniza los estados iniciales del dominio.
   *
   * Flujo:
   * 1. Publica `firstJob` en la cola `skill_jobs`.
   * 2. Marca el `workflow_step` como `ENQUEUED`.
   * 3. Marca el `workflow_run` como `RUNNING`.
   * 4. Marca el `requirement` como `RUNNING`.
   *
   * Si la publicacion falla:
   * - marca el job como `FAILED`
   * - marca el step como `FAILED`
   * - marca el workflow como `FAILED`
   * - marca el requirement como `FAILED`
   *
   * Eso evita dejar el sistema en un estado ambiguo donde la base crea que
   * existe un flujo en curso pero RabbitMQ nunca recibio el trabajo.
   */
  private async publishFirstJob(result: WorkflowLaunchResult) {
    const firstStep = requireFirstItem(
      result.workflowSteps,
      "publishing the first workflow job",
    );

    try {
      await publishJson(
        this.publisherChannel,
        env.skillJobsQueue,
        buildSkillJobMessage(result.firstJob),
      );
      result.workflowSteps[0] = await this.workflowStepsRepository.markEnqueued(
        firstStep.id,
        result.firstJob.id,
      );
      result.workflowRun = await this.workflowRunsRepository.markRunning(
        result.workflowRun.id,
        firstStep.stepName,
      );
      result.requirement = await this.requirementsRepository.markStatus(
        result.requirement.id,
        "RUNNING",
      );
    } catch (error) {
      const message = `Unable to publish job ${result.firstJob.id} to ${env.skillJobsQueue}: ${getErrorMessage(error)}`;
      await this.jobsRepository.markQueuePublishFailed(result.firstJob.id, message);
      await this.workflowStepsRepository.markFailed(
        firstStep.id,
        message,
        result.firstJob.id,
      );
      await this.workflowRunsRepository.markFailed(result.workflowRun.id, message);
      await this.requirementsRepository.markStatus(result.requirement.id, "FAILED");
      throw new QueuePublishError(message);
    }
  }

  /**
   * Lanza una ejecucion standalone usando el mismo modelo nuevo
   * `requirement -> workflow_run -> workflow_step -> job`.
   *
   * Aunque el usuario entre por `POST /jobs`, internamente hacemos esto:
   * 1. Validamos que la skill exista.
   * 2. Pedimos a PostgreSQL un `requirement_code`.
   * 3. Creamos la carpeta del caso y el snapshot del request.
   * 4. Creamos un workflow_run llamado `standalone`.
   * 5. Creamos un solo workflow_step asociado a esa skill.
   * 6. Creamos el job operativo.
   * 7. Publicamos ese job.
   *
   * De esta forma ya no existen "jobs sueltos" a nivel de arquitectura,
   * aunque la API siga exponiendo `/jobs` para backward compatibility.
   */
  async launchStandalone(input: CreateJobRequest) {
    if (!isRegisteredSkill(input.skillName)) {
      throw new UnsupportedSkillError(input.skillName);
    }

    const requirementCode = await this.requirementsRepository.reserveRequirementCode();
    const workspace = await ensureRequirementWorkspace(env.projectRoot, requirementCode, {
      requirementCode,
      executionMode: "standalone",
      workflowName: "standalone",
      skillName: input.skillName,
      notifyEmail: input.notifyEmail,
      payload: input.payload,
    });
    const stepWorkspace = await ensureWorkflowStepWorkspace(
      workspace.caseRootDir,
      input.skillName,
    );
    const stepPayload = buildStandaloneStepPayload(
      input.skillName,
      input.payload,
      workspace.requestSnapshotPath,
      workspace.caseRootDir,
      stepWorkspace.stepOutputDir,
    );

    const result = await withTransaction(async (client) => {
      // Resuelve un nombre humano legible para el caso si el payload lo permite.
      const caseName = inferCaseName(input.payload, input.caseName);

      // Crea la entidad principal del caso. A partir de aqui ya existe un
      // requirement formal con carpeta y metadata persistida.
      const requirement = await this.requirementsRepository.create(
        {
          requirementCode,
          ...(caseName ? { caseName } : {}),
          notifyEmail: input.notifyEmail,
          rootDir: workspace.caseRootDir,
          inputPayload: input.payload,
        },
        client,
      );

      // Crea un workflow_run de un solo paso. Aunque sea standalone,
      // mantenemos el mismo modelo que usaremos para pipelines completos.
      const workflowRun = await this.workflowRunsRepository.create(
        {
          requirementId: requirement.id,
          workflowName: "standalone",
          executionMode: "standalone",
          inputPayload: input.payload,
        },
        client,
      );

      // Registra el unico step del workflow standalone. Arranca en READY
      // porque no depende de ningun otro step previo.
      const workflowSteps = await this.workflowStepsRepository.createMany(
        [
          {
            workflowRunId: workflowRun.id,
            stepName: input.skillName,
            skillName: input.skillName,
            sequenceOrder: 0,
            status: "READY",
            producedArtifactTypes: [],
            requiredArtifactTypes: ["request_input"],
            stepPayload,
          },
        ],
        client,
      );

      // Obtiene el primer step para usarlo como origen del primer job.
      const firstStep = requireFirstItem(
        workflowSteps,
        "creating the first standalone workflow step",
      );

      // Crea el job operativo que consumira el worker.
      // Aqui ya quedan asociadas todas las referencias del modelo:
      // requirement, workflow_run, workflow_step y directorios fisicos.
      const firstJob = await this.jobsRepository.createPendingJob(
        {
          skillName: input.skillName,
          payload: stepPayload,
          notificationEmail: input.notifyEmail,
          requirementCode,
          requirementUuid: requirement.id,
          executionMode: "standalone",
          workflowName: "standalone",
          stepName: firstStep.stepName,
          workflowRunId: workflowRun.id,
          workflowStepId: firstStep.id,
          caseRootDir: workspace.caseRootDir,
          outputDir: stepWorkspace.stepOutputDir,
        },
        client,
      );

      return {
        requirement,
        workflowRun,
        workflowSteps,
        firstJob,
      };
    });

    // La publicacion queda fuera de la transaccion para no abrir una TX de DB
    // mientras esperamos confirmacion del broker.
    await this.publishFirstJob(result);
    return result;
  }

  /**
   * Lanza un workflow orquestado completo a partir de una definicion declarada
   * en `workflow-definitions.ts`.
   *
   * Flujo:
   * 1. Valida que el workflow exista y que todas sus skills esten registradas.
   * 2. Reserva un requirement_code en PostgreSQL.
   * 3. Crea la carpeta del requirement y una carpeta por step.
   * 4. En una transaccion crea:
   *    - requirement
   *    - workflow_run
   *    - workflow_steps
   *    - firstJob
   * 5. Publica solo el primer job.
   *
   * Importante:
   * - este metodo NO ejecuta aun los siguientes steps automaticamente;
   *   solo deja sembrado el workflow en DB y dispara el primer step.
   * - la continuidad `design -> quote -> proposal` dependera del reconciliador
   *   que correra al terminar cada job.
   */
  async launchWorkflowRun(input: CreateWorkflowRunRequest) {
    // Carga la definicion declarativa del workflow y valida que el worker
    // conozca todas las skills involucradas.
    const definition = assertWorkflowSkillsRegistered(input.workflowName);

    // Pide a PostgreSQL el codigo visible del caso para garantizar unicidad
    // real bajo concurrencia.
    const requirementCode = await this.requirementsRepository.reserveRequirementCode();

    // Crea la carpeta raiz del case y persiste el JSON original del request.
    const workspace = await ensureRequirementWorkspace(env.projectRoot, requirementCode, {
      requirementCode,
      executionMode: definition.executionMode,
      workflowName: definition.workflowName,
      notifyEmail: input.notifyEmail,
      payload: input.payload,
    });

    // Prepara la carpeta fisica de salida de cada step antes de abrir la
    // transaccion. Ejemplo:
    // /output/REQ-0001/design/
    // /output/REQ-0001/quote/
    // /output/REQ-0001/proposal/
    // Asi las rutas quedan definidas desde el arranque del workflow.
    const stepWorkspaces = new Map<string, string>();
    for (const step of definition.steps) {
      const stepWorkspace = await ensureWorkflowStepWorkspace(
        workspace.caseRootDir,
        step.stepName,
      );
      stepWorkspaces.set(step.stepName, stepWorkspace.stepOutputDir);
    }

    const result = await withTransaction(async (client) => {
      // Igual que en standalone, intentamos inferir un nombre legible del caso.
      const caseName = inferCaseName(input.payload, input.caseName);

      // Crea el requirement, que es el verdadero contenedor del caso completo.
      const requirement = await this.requirementsRepository.create(
        {
          requirementCode,
          ...(caseName ? { caseName } : {}),
          notifyEmail: input.notifyEmail,
          rootDir: workspace.caseRootDir,
          inputPayload: input.payload,
        },
        client,
      );

      // Crea la corrida concreta del workflow para este requirement.
      const workflowRun = await this.workflowRunsRepository.create(
        {
          requirementId: requirement.id,
          workflowName: definition.workflowName,
          executionMode: definition.executionMode,
          inputPayload: input.payload,
        },
        client,
      );

      // Crea todos los steps del workflow, dejando solo el primero en READY
      // y el resto en PENDING hasta que el reconciliador los habilite.
      const workflowSteps = await this.workflowStepsRepository.createMany(
        definition.steps.map((step, index) => ({
          workflowRunId: workflowRun.id,
          stepName: step.stepName,
          skillName: step.skillName,
          sequenceOrder: step.sequenceOrder,
          status: index === 0 ? "READY" : "PENDING",
          dependsOnSteps: step.dependsOnSteps,
          requiredArtifactTypes: step.requiredArtifactTypes,
          producedArtifactTypes: step.producedArtifactTypes,
          stepPayload: buildWorkflowStepPayload(
            step,
            workspace.requestSnapshotPath,
            workspace.caseRootDir,
            stepWorkspaces.get(step.stepName) ?? workspace.caseRootDir,
            input.payload,
          ),
        })),
        client,
      );

      // Toma el primer step como punto de arranque del pipeline.
      const firstStep = requireFirstItem(
        workflowSteps,
        "creating the first workflow step",
      );

      // Crea el job operativo inicial. Ese job es el unico que se encola
      // en esta fase; los siguientes se derivaran despues segun los resultados.
      const firstJob = await this.jobsRepository.createPendingJob(
        {
          skillName: firstStep.skillName,
          payload: firstStep.stepPayload,
          notificationEmail: input.notifyEmail,
          requirementCode,
          requirementUuid: requirement.id,
          executionMode: definition.executionMode,
          workflowName: workflowRun.workflowName,
          stepName: firstStep.stepName,
          workflowRunId: workflowRun.id,
          workflowStepId: firstStep.id,
          caseRootDir: workspace.caseRootDir,
          outputDir: stepWorkspaces.get(firstStep.stepName) ?? workspace.caseRootDir,
        },
        client,
      );

      return {
        requirement,
        workflowRun,
        workflowSteps,
        firstJob,
      };
    });

    // Publica el primer job y actualiza el estado global del workflow.
    await this.publishFirstJob(result);
    return result;
  }
}
