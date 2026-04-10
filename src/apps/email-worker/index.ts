import type { ConsumeMessage } from "amqplib";
import nodemailer from "nodemailer";
import { ZodError } from "zod";

import { env } from "../../shared/config/env.js";
import { JobsRepository } from "../../shared/db/jobs-repository.js";
import {
  assertDatabaseConnection,
  closeDatabaseConnection,
} from "../../shared/db/postgres.js";
import { emailJobMessageSchema } from "../../shared/jobs/job-types.js";
import { createLogger, getErrorMessage } from "../../shared/logging/logger.js";
import {
  closeRabbitConnection,
  createConsumerChannel,
  createRabbitConnection,
  parseMessage,
} from "../../shared/rabbitmq/rabbitmq.js";

const logger = createLogger("worker:email");

function createTransport() {
  return nodemailer.createTransport({
    host: env.smtpHost,
    port: env.smtpPort,
    secure: env.smtpSecure,
    auth: env.smtpUser
      ? {
          user: env.smtpUser,
          pass: env.smtpPass ?? "",
        }
      : undefined,
  });
}

function buildEmailText(job: Awaited<ReturnType<JobsRepository["findById"]>>) {
  if (!job) {
    return "The job could not be found in the database.";
  }

  return [
    `Job ID: ${job.id}`,
    `Skill: ${job.skillName}`,
    `Status: ${job.status}`,
    `Attempts: ${job.attempts}`,
    `Started At: ${job.startedAt?.toISOString() ?? "N/A"}`,
    `Finished At: ${job.finishedAt?.toISOString() ?? "N/A"}`,
    `Output File: ${job.outputFile ?? "N/A"}`,
    `Error: ${job.errorMessage ?? "N/A"}`,
  ].join("\n");
}

async function sendEmail(
  transporter: ReturnType<typeof createTransport>,
  to: string,
  subject: string,
  text: string,
) {
  await transporter.sendMail({
    from: env.smtpFrom,
    to,
    subject,
    text,
  });
}

async function main() {
  await assertDatabaseConnection();

  const transporter = createTransport();
  await transporter.verify();  // ← verifica que SMTP responde antes de arrancar

  const rabbitConnection = await createRabbitConnection();
  const consumerChannel = await createConsumerChannel(rabbitConnection);
  const jobsRepository = new JobsRepository();

  async function handleMessage(message: ConsumeMessage) {
    const payload = parseMessage(message, emailJobMessageSchema);
    const job = await jobsRepository.findById(payload.jobId);

    if (!job) {
      // descarta, no hay nada que notificar
      logger.error("Dropping email job because the database record does not exist", {
        jobId: payload.jobId,
      });
      consumerChannel.ack(message);
      return;
    }

    if (job.notificationStatus === "SENT") {
       // idempotente, no manda dos veces
      consumerChannel.ack(message);
      return;
    }

    await sendEmail(
      transporter,
      payload.notifyEmail,
      `Job ${job.id} finished with status ${job.status}`,
      buildEmailText(job),
    );

    await jobsRepository.markNotificationSent(job.id);
    consumerChannel.ack(message);
  }

  await consumerChannel.consume(
    env.emailJobsQueue,
    async (message: ConsumeMessage | null) => {
      if (!message) {
        return;
      }

      try {
        await handleMessage(message);
      } catch (error) {
        if (error instanceof ZodError || error instanceof SyntaxError) {
          logger.error("Dropping malformed email queue message", {
            error,
            redelivered: message.fields.redelivered,
          });
          consumerChannel.ack(message);
          return;
        }

        logger.error("Email worker failed to process message", {
          error,
          redelivered: message.fields.redelivered,
        });

        try {
          const payload = parseMessage(message, emailJobMessageSchema);
          await jobsRepository.markNotificationFailed(
            payload.jobId,
            getErrorMessage(error),
          );
        } catch (markError) {
          logger.error("Could not persist email failure state", {
            error: markError,
          });
        }

        consumerChannel.nack(message, false, true);
      }
    },
    { noAck: false },
  );

  logger.info("Email worker consuming queue", {
    queue: env.emailJobsQueue,
  });

  const shutdown = async (signal: string) => {
    logger.info("Shutdown requested", { signal });
    await consumerChannel.close();
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
  logger.error("Email worker boot failed", { error });
  await closeDatabaseConnection();
  process.exit(1);
});
