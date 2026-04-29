import type { ConsumeMessage } from "amqplib";
import { ZodError } from "zod";

import { env } from "../../shared/config/env.js";
import { JobsRepository } from "../../shared/db/jobs-repository.js";
import {
  ArtifactsRepository,
  RequirementsRepository,
  WorkflowRunsRepository,
  WorkflowStepsRepository,
} from "../../shared/db/workflow-repository.js";
import {
  assertDatabaseConnection,
  closeDatabaseConnection,
} from "../../shared/db/postgres.js";
import {
  buildEmailJobMessage,
  skillJobMessageSchema,
} from "../../shared/jobs/job-types.js";
import {
  UnknownSkillError,
  resolveSkillExecution,
} from "../../shared/jobs/skill-registry.js";
import { createLogger, getErrorMessage } from "../../shared/logging/logger.js";
import { runSpawnedProcess } from "../../shared/processes/run-spawned-process.js";
import {
  closeRabbitConnection,
  createConsumerChannel,
  createPublisherChannel,
  createRabbitConnection,
  parseMessage,
  publishJson,
} from "../../shared/rabbitmq/rabbitmq.js";
import { WorkflowOrchestratorService } from "../../shared/workflows/workflow-orchestrator.js";

const logger = createLogger("worker:skill");

async function main() {
  await assertDatabaseConnection();

  const rabbitConnection = await createRabbitConnection();
  const consumerChannel = await createConsumerChannel(rabbitConnection);
  const publisherChannel = await createPublisherChannel(rabbitConnection);
  const jobsRepository = new JobsRepository();
  const workflowOrchestrator = new WorkflowOrchestratorService(
    new RequirementsRepository(),
    new WorkflowRunsRepository(),
    new WorkflowStepsRepository(),
    new ArtifactsRepository(),
    jobsRepository,
    publisherChannel,
  );

  async function enqueueEmailNotification(jobId: string) {
    const job = await jobsRepository.findById(jobId);

    if (!job) {
      throw new Error(`Job ${jobId} not found while preparing email notification.`);
    }

    if (job.notificationStatus === "SENT") {
      return;
    }

    await publishJson(
      publisherChannel,
      env.emailJobsQueue,
      buildEmailJobMessage(job),
    );
    await jobsRepository.markNotificationQueued(job.id);
  }

  async function handleMessage(message: ConsumeMessage) {
    const payload = parseMessage(message, skillJobMessageSchema);
    const job = await jobsRepository.findById(payload.jobId);

    if (!job) {
      logger.error("Dropping skill job because it does not exist in the database", {
        jobId: payload.jobId,
      });
      consumerChannel.ack(message);
      return;
    }

    if (job.status === "COMPLETED" || job.status === "FAILED") {
      if (job.notificationStatus !== "SENT") {
        await enqueueEmailNotification(job.id);
      }

      consumerChannel.ack(message);
      return;
    }

    const runningJob = await jobsRepository.markRunning(job.id);

    if (!runningJob) {
      logger.warn("Skipping job because it could not be moved to RUNNING", {
        jobId: job.id,
        status: job.status,
      });
      consumerChannel.ack(message);
      return;
    }

    logger.info("Worker picked job", {
      jobId: runningJob.id,
      skillName: runningJob.skillName,
      requirementId: runningJob.requirementId,
      requirementUuid: runningJob.requirementUuid,
      workflowName: runningJob.workflowName,
      workflowRunId: runningJob.workflowRunId,
      workflowStepId: runningJob.workflowStepId,
      stepName: runningJob.stepName,
      caseRootDir: runningJob.caseRootDir,
      outputDir: runningJob.outputDir,
    });

    try {
      await workflowOrchestrator.handleJobStarted(runningJob);

      const execution = resolveSkillExecution(
        runningJob.skillName,
        runningJob.payload,
        env,
      );
      const result = await runSpawnedProcess(
        execution,
        env.maxProcessOutputChars,
      );

      if (result.exitCode === 0) {
        const completedJob = await jobsRepository.markCompleted(runningJob.id, {
          stdout: result.stdout || null,
          stderr: result.stderr || null,
          outputFile: execution.outputFile ?? null,
          exitCode: result.exitCode,
        });

        logger.info("Worker completed job", {
          jobId: completedJob.id,
          skillName: completedJob.skillName,
          requirementId: completedJob.requirementId,
          workflowRunId: completedJob.workflowRunId,
          workflowStepId: completedJob.workflowStepId,
          stepName: completedJob.stepName,
          outputFile: completedJob.outputFile,
          exitCode: completedJob.exitCode,
        });

        await reconcileWorkflowIfNeeded(workflowOrchestrator, completedJob);
      } else {
        const failedJob = await jobsRepository.markFailed(runningJob.id, {
          stdout: result.stdout || null,
          stderr: result.stderr || null,
          outputFile: execution.outputFile ?? null,
          exitCode: result.exitCode,
          errorMessage: `Skill exited with code ${String(result.exitCode ?? "unknown")}.`,
        });

        logger.warn("Worker finished job with non-zero exit code", {
          jobId: failedJob.id,
          skillName: failedJob.skillName,
          requirementId: failedJob.requirementId,
          workflowRunId: failedJob.workflowRunId,
          workflowStepId: failedJob.workflowStepId,
          stepName: failedJob.stepName,
          outputFile: failedJob.outputFile,
          exitCode: failedJob.exitCode,
          errorMessage: failedJob.errorMessage,
        });

        await reconcileWorkflowIfNeeded(workflowOrchestrator, failedJob);
      }
    } catch (error) {
      const errorMessage =
        error instanceof UnknownSkillError
          ? error.message
          : `Skill execution failed: ${getErrorMessage(error)}`;

      const failedJob = await jobsRepository.markFailed(runningJob.id, {
        stdout: null,
        stderr: null,
        outputFile: null,
        exitCode: null,
        errorMessage,
      });

      logger.error("Worker failed job while executing skill", {
        jobId: failedJob.id,
        skillName: failedJob.skillName,
        requirementId: failedJob.requirementId,
        workflowRunId: failedJob.workflowRunId,
        workflowStepId: failedJob.workflowStepId,
        stepName: failedJob.stepName,
        errorMessage: failedJob.errorMessage,
      });

      await reconcileWorkflowIfNeeded(workflowOrchestrator, failedJob);
    }

    await enqueueEmailNotification(runningJob.id);
    logger.info("Worker queued email notification", {
      jobId: runningJob.id,
      requirementId: runningJob.requirementId,
      workflowRunId: runningJob.workflowRunId,
      workflowStepId: runningJob.workflowStepId,
      stepName: runningJob.stepName,
    });
    consumerChannel.ack(message);
  }

  await consumerChannel.consume(
    env.skillJobsQueue,
    async (message: ConsumeMessage | null) => {
      if (!message) {
        return;
      }

      try {
        await handleMessage(message);
      } catch (error) {
        if (error instanceof ZodError || error instanceof SyntaxError) {
          logger.error("Dropping malformed skill queue message", {
            error,
            redelivered: message.fields.redelivered,
          });
          consumerChannel.ack(message);
          return;
        }

        logger.error("Skill worker failed to process message", {
          error,
          redelivered: message.fields.redelivered,
        });

        consumerChannel.nack(message, false, true);
      }
    },
    { noAck: false },
  );

  logger.info("Skill worker consuming queue", {
    queue: env.skillJobsQueue,
  });

  const shutdown = async (signal: string) => {
    logger.info("Shutdown requested", { signal });
    await consumerChannel.close();
    await publisherChannel.close();
    await closeRabbitConnection(rabbitConnection);
    await closeDatabaseConnection();
    process.exit(0);
  };

  process.on("SIGINT", () => {
    void shutdown("SIGINT");
  });

  process.on("SIGTERM", () => {
    void shutdown("SIGTERM");
  });
}

async function reconcileWorkflowIfNeeded(
  workflowOrchestrator: WorkflowOrchestratorService,
  job: Awaited<ReturnType<JobsRepository["markCompleted"]>>,
) {
  try {
    await workflowOrchestrator.reconcileAfterJob(job);
  } catch (error) {
    logger.error("Workflow reconciliation failed after terminal job update", {
      jobId: job.id,
      error,
    });
  }
}

void main().catch(async (error) => {
  logger.error("Skill worker boot failed", { error });
  await closeDatabaseConnection();
  process.exit(1);
});
