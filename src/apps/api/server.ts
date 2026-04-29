import type { Server } from "node:http";

import { env } from "../../shared/config/env.js";
import { JobsRepository } from "../../shared/db/jobs-repository.js";
import {
  RequirementsRepository,
  WorkflowRunsRepository,
  WorkflowStepsRepository,
} from "../../shared/db/workflow-repository.js";
import {
  assertDatabaseConnection,
  closeDatabaseConnection,
} from "../../shared/db/postgres.js";
import { createLogger } from "../../shared/logging/logger.js";
import {
  closeRabbitConnection,
  createPublisherChannel,
  createRabbitConnection,
} from "../../shared/rabbitmq/rabbitmq.js";
import { createApp } from "./app.js";
import { JobsService } from "./services/jobs-service.js";
import { WorkflowLaunchService } from "./services/workflow-launch-service.js";
import { WorkflowRunsService } from "./services/workflow-runs-service.js";

const logger = createLogger("api:server");

async function main() {
  await assertDatabaseConnection();

  const rabbitConnection = await createRabbitConnection();
  const publisherChannel = await createPublisherChannel(rabbitConnection);

  const jobsRepository = new JobsRepository();
  const requirementsRepository = new RequirementsRepository();
  const workflowRunsRepository = new WorkflowRunsRepository();
  const workflowStepsRepository = new WorkflowStepsRepository();
  const workflowLaunchService = new WorkflowLaunchService(
    requirementsRepository,
    workflowRunsRepository,
    workflowStepsRepository,
    jobsRepository,
    publisherChannel,
  );
  const jobsService = new JobsService(jobsRepository, workflowLaunchService);
  const workflowRunsService = new WorkflowRunsService(workflowLaunchService);
  const app = createApp(jobsService, workflowRunsService);

  const server = await new Promise<Server>((resolveServer) => {
    const instance = app.listen(env.port, () => {
      logger.info("API listening", { port: env.port });
      resolveServer(instance);
    });
  });

  const shutdown = async (signal: string) => {
    logger.info("Shutdown requested", { signal });

    await new Promise<void>((resolveClose, rejectClose) => {
      server.close((error) => {
        if (error) {
          rejectClose(error);
          return;
        }

        resolveClose();
      });
    });

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

void main().catch(async (error) => {
  logger.error("API boot failed", { error });
  await closeDatabaseConnection();
  process.exit(1);
});
