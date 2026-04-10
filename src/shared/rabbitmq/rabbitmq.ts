import amqp, {
  type Channel,
  type ChannelModel,
  type ConfirmChannel,
  type ConsumeMessage,
  type Options,
} from "amqplib";
import { z } from "zod";

import { env } from "../config/env.js";
import { createLogger } from "../logging/logger.js";

const logger = createLogger("shared:rabbitmq");
/*Tiempo de espera para el reintento */

function sleep(milliseconds: number) {
  return new Promise((resolveDelay) => {
    setTimeout(resolveDelay, milliseconds);
  });
}
/*Cola donde llegan los mensajes fallidos para que no se pierdan */

function buildQueueArguments(routingKey?: string) {
  if (!env.rabbitMqDlxName || !routingKey) {
    return undefined;
  }

  return {
    "x-dead-letter-exchange": env.rabbitMqDlxName,
    "x-dead-letter-routing-key": routingKey,
  };
}
/*Se crea la cola, si existe la usa */
async function assertTopology(channel: Channel | ConfirmChannel) {
  await channel.assertQueue(env.skillJobsQueue, {
    durable: true,
    arguments: buildQueueArguments(env.skillDlxRoutingKey),
  });

  await channel.assertQueue(env.emailJobsQueue, {
    durable: true,
    arguments: buildQueueArguments(env.emailDlxRoutingKey),
  });
}
/*Conexion con reintentes*/
export async function createRabbitConnection() {
  let lastError: unknown;

  for (let attempt = 1; attempt <= env.rabbitMqConnectRetries; attempt += 1) {
    try {
      const connection = await amqp.connect(env.rabbitMqUrl);
      logger.info("RabbitMQ connection ready", { attempt });
      return connection;
    } catch (error) {
      lastError = error;

      logger.warn("RabbitMQ connection attempt failed", {
        attempt,
        maxAttempts: env.rabbitMqConnectRetries,
        retryInMs: env.rabbitMqConnectDelayMs,
      });

      if (attempt < env.rabbitMqConnectRetries) {
        await sleep(env.rabbitMqConnectDelayMs);
      }
    }
  }

  throw lastError;
}

export async function createConsumerChannel(connection: ChannelModel) {
  const channel = await connection.createChannel();
  await assertTopology(channel);
  await channel.prefetch(env.rabbitMqPrefetch);
  return channel;
}

export async function createPublisherChannel(connection: ChannelModel) {
  const channel = await connection.createConfirmChannel();
  await assertTopology(channel);
  return channel;
}

export async function publishJson(
  channel: ConfirmChannel,
  queue: string,
  payload: unknown,
  options?: Options.Publish,
) {
  channel.sendToQueue(queue, Buffer.from(JSON.stringify(payload)), {
    persistent: true,
    contentType: "application/json",
    ...options,
  });

  await channel.waitForConfirms();
}

export function parseMessage<T>(message: ConsumeMessage, schema: z.ZodSchema<T>) {
  const parsed = JSON.parse(message.content.toString()) as unknown;
  return schema.parse(parsed);
}

export async function closeRabbitConnection(connection: ChannelModel | null) {
  if (connection) {
    await connection.close();
  }
}
