import { z } from "zod";

export const jobStatusSchema = z.enum([
  "PENDING",
  "RUNNING",
  "COMPLETED",
  "FAILED",
]);

export const notificationStatusSchema = z.enum([
  "PENDING",
  "QUEUED",
  "SENT",
  "FAILED",
]);

export const executionModeSchema = z.enum(["standalone", "workflow"]);

export const jobPayloadSchema = z.record(z.string(), z.unknown());

export const createJobRequestSchema = z
  .object({
    skillName: z.string().min(1),
    notifyEmail: z.string().email(),
    caseName: z.string().min(1).optional(),
    payload: jobPayloadSchema.default({}),
  })
  .strict();

export const jobIdParamsSchema = z.object({
  id: z.string().uuid(),
});

export const skillJobMessageSchema = z.object({
  jobId: z.string().uuid(),
  skillName: z.string().min(1),
  notifyEmail: z.string().email(),
  requirementId: z.string().min(1).optional(),
  requirementUuid: z.string().uuid().nullable().optional(),
  executionMode: executionModeSchema.optional(),
  workflowName: z.string().min(1).nullable().optional(),
  stepName: z.string().min(1).nullable().optional(),
  workflowRunId: z.string().uuid().nullable().optional(),
  workflowStepId: z.string().uuid().nullable().optional(),
  caseRootDir: z.string().min(1).nullable().optional(),
  outputDir: z.string().min(1).nullable().optional(),
  payload: jobPayloadSchema,
  createdAt: z.string().datetime(),
});

export const emailJobMessageSchema = z.object({
  jobId: z.string().uuid(),
  skillName: z.string().min(1),
  notifyEmail: z.string().email(),
  status: jobStatusSchema,
  errorMessage: z.string().nullable(),
  outputFile: z.string().nullable(),
  finishedAt: z.string().nullable(),
});

export type JobStatus = z.infer<typeof jobStatusSchema>;
export type NotificationStatus = z.infer<typeof notificationStatusSchema>;
export type ExecutionMode = z.infer<typeof executionModeSchema>;
export type JobPayload = z.infer<typeof jobPayloadSchema>;
export type CreateJobRequest = z.infer<typeof createJobRequestSchema>;
export type SkillJobMessage = z.infer<typeof skillJobMessageSchema>;
export type EmailJobMessage = z.infer<typeof emailJobMessageSchema>;

export interface JobRecord {
  id: string;
  skillName: string;
  status: JobStatus;
  notificationEmail: string;
  notificationStatus: NotificationStatus;
  requirementId: string | null;
  requirementUuid: string | null;
  executionMode: ExecutionMode;
  workflowName: string | null;
  stepName: string | null;
  workflowRunId: string | null;
  workflowStepId: string | null;
  caseRootDir: string | null;
  outputDir: string | null;
  payload: JobPayload;
  attempts: number;
  stdout: string | null;
  stderr: string | null;
  errorMessage: string | null;
  outputFile: string | null;
  exitCode: number | null;
  startedAt: Date | null;
  finishedAt: Date | null;
  notificationQueuedAt: Date | null;
  notificationSentAt: Date | null;
  notificationError: string | null;
  createdAt: Date;
  updatedAt: Date;
}

export function serializeJob(job: JobRecord) {
  return {
    id: job.id,
    skillName: job.skillName,
    status: job.status,
    notificationEmail: job.notificationEmail,
    notificationStatus: job.notificationStatus,
    requirementId: job.requirementId,
    requirementUuid: job.requirementUuid,
    executionMode: job.executionMode,
    workflowName: job.workflowName,
    stepName: job.stepName,
    workflowRunId: job.workflowRunId,
    workflowStepId: job.workflowStepId,
    caseRootDir: job.caseRootDir,
    outputDir: job.outputDir,
    payload: job.payload,
    attempts: job.attempts,
    stdout: job.stdout,
    stderr: job.stderr,
    errorMessage: job.errorMessage,
    outputFile: job.outputFile,
    exitCode: job.exitCode,
    startedAt: job.startedAt?.toISOString() ?? null,
    finishedAt: job.finishedAt?.toISOString() ?? null,
    notificationQueuedAt: job.notificationQueuedAt?.toISOString() ?? null,
    notificationSentAt: job.notificationSentAt?.toISOString() ?? null,
    notificationError: job.notificationError,
    createdAt: job.createdAt.toISOString(),
    updatedAt: job.updatedAt.toISOString(),
  };
}

export function buildSkillJobMessage(job: JobRecord): SkillJobMessage {
  return {
    jobId: job.id,
    skillName: job.skillName,
    notifyEmail: job.notificationEmail,
    requirementId: job.requirementId ?? undefined,
    requirementUuid: job.requirementUuid,
    executionMode: job.executionMode,
    workflowName: job.workflowName,
    stepName: job.stepName,
    workflowRunId: job.workflowRunId,
    workflowStepId: job.workflowStepId,
    caseRootDir: job.caseRootDir,
    outputDir: job.outputDir,
    payload: job.payload,
    createdAt: job.createdAt.toISOString(),
  };
}

export function buildEmailJobMessage(job: JobRecord): EmailJobMessage {
  return {
    jobId: job.id,
    skillName: job.skillName,
    notifyEmail: job.notificationEmail,
    status: job.status,
    errorMessage: job.errorMessage,
    outputFile: job.outputFile,
    finishedAt: job.finishedAt?.toISOString() ?? null,
  };
}
