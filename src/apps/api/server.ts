import type { Server } from "node:http";

import { env } from "../../shared/config/env.js";
import { JobsRepository } from "../../shared/db/jobs-repository.js";
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

const logger = createLogger("api:server");

async function main() {
  await assertDatabaseConnection();

  const rabbitConnection = await createRabbitConnection();
  const publisherChannel = await createPublisherChannel(rabbitConnection);

  const jobsRepository = new JobsRepository();
  const jobsService = new JobsService(jobsRepository, publisherChannel);
  const app = createApp(jobsService);

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
