import { config as loadEnv } from "dotenv";
import { z } from "zod";

loadEnv();

const envSchema = z.object({
  NODE_ENV: z.enum(["development", "test", "production"]).default("development"),
  PORT: z.coerce.number().int().positive().default(3000),
  DATABASE_URL: z
    .string()
    .min(1)
    .default("postgresql://codex:codex@localhost:5432/codex_jobs"),
  RABBITMQ_URL: z.string().min(1).default("amqp://guest:guest@localhost:5672"),
  RABBITMQ_PREFETCH: z.coerce.number().int().positive().default(1),
  RABBITMQ_CONNECT_RETRIES: z.coerce.number().int().positive().default(10),
  RABBITMQ_CONNECT_DELAY_MS: z.coerce.number().int().positive().default(3000),
  SKILL_JOBS_QUEUE: z.string().min(1).default("skill_jobs"),
  EMAIL_JOBS_QUEUE: z.string().min(1).default("email_jobs"),
  SMTP_HOST: z.string().min(1).default("localhost"),
  SMTP_PORT: z.coerce.number().int().positive().default(1025),
  SMTP_SECURE: z
    .string()
    .optional()
    .default("false")
    .transform((value) => value.toLowerCase() === "true"),
  SMTP_USER: z.string().optional(),
  SMTP_PASS: z.string().optional(),
  SMTP_FROM: z.string().min(1).default("no-reply@codex.local"),
  PROJECT_ROOT: z.string().min(1).default(process.cwd()),
  MAX_PROCESS_OUTPUT_CHARS: z.coerce.number().int().positive().default(20000),
  RABBITMQ_DLX_NAME: z.string().optional(),
  SKILL_DLX_ROUTING_KEY: z.string().optional(),
  EMAIL_DLX_ROUTING_KEY: z.string().optional(),
});

const parsedEnv = envSchema.parse(process.env);

export const env = {
  nodeEnv: parsedEnv.NODE_ENV,
  port: parsedEnv.PORT,
  databaseUrl: parsedEnv.DATABASE_URL,
  rabbitMqUrl: parsedEnv.RABBITMQ_URL,
  rabbitMqPrefetch: parsedEnv.RABBITMQ_PREFETCH,
  rabbitMqConnectRetries: parsedEnv.RABBITMQ_CONNECT_RETRIES,
  rabbitMqConnectDelayMs: parsedEnv.RABBITMQ_CONNECT_DELAY_MS,
  skillJobsQueue: parsedEnv.SKILL_JOBS_QUEUE,
  emailJobsQueue: parsedEnv.EMAIL_JOBS_QUEUE,
  smtpHost: parsedEnv.SMTP_HOST,
  smtpPort: parsedEnv.SMTP_PORT,
  smtpSecure: parsedEnv.SMTP_SECURE,
  smtpUser: parsedEnv.SMTP_USER,
  smtpPass: parsedEnv.SMTP_PASS,
  smtpFrom: parsedEnv.SMTP_FROM,
  projectRoot: parsedEnv.PROJECT_ROOT,
  maxProcessOutputChars: parsedEnv.MAX_PROCESS_OUTPUT_CHARS,
  rabbitMqDlxName: parsedEnv.RABBITMQ_DLX_NAME,
  skillDlxRoutingKey: parsedEnv.SKILL_DLX_ROUTING_KEY,
  emailDlxRoutingKey: parsedEnv.EMAIL_DLX_ROUTING_KEY,
} as const;

export type AppEnvironment = typeof env;
