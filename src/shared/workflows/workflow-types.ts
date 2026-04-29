import { z } from "zod";

import { jobPayloadSchema, serializeJob, type JobRecord } from "../jobs/job-types.js";

export const requirementStatusSchema = z.enum([
  "CREATED",
  "RUNNING",
  "COMPLETED",
  "FAILED",
  "PARTIAL",
]);

export const workflowRunStatusSchema = z.enum([
  "CREATED",
  "RUNNING",
  "COMPLETED",
  "FAILED",
  "CANCELLED",
]);

export const workflowStepStatusSchema = z.enum([
  "PENDING",
  "READY",
  "ENQUEUED",
  "RUNNING",
  "COMPLETED",
  "FAILED",
  "BLOCKED",
  "SKIPPED",
]);

export const createWorkflowRunRequestSchema = z.object({
  workflowName: z.string().min(1),
  notifyEmail: z.string().email(),
  caseName: z.string().min(1).optional(),
  payload: jobPayloadSchema.default({}),
});

export type RequirementStatus = z.infer<typeof requirementStatusSchema>;
export type WorkflowRunStatus = z.infer<typeof workflowRunStatusSchema>;
export type WorkflowStepStatus = z.infer<typeof workflowStepStatusSchema>;
export type CreateWorkflowRunRequest = z.infer<typeof createWorkflowRunRequestSchema>;

export interface RequirementRecord {
  id: string;
  requirementCode: string;
  caseName: string | null;
  notifyEmail: string;
  rootDir: string;
  status: RequirementStatus;
  inputPayload: Record<string, unknown>;
  createdAt: Date;
  updatedAt: Date;
}

export interface WorkflowRunRecord {
  id: string;
  requirementId: string;
  workflowName: string;
  executionMode: "standalone" | "workflow";
  status: WorkflowRunStatus;
  currentStepName: string | null;
  notifyOnCompletion: boolean;
  inputPayload: Record<string, unknown>;
  startedAt: Date | null;
  finishedAt: Date | null;
  lastError: string | null;
  createdAt: Date;
  updatedAt: Date;
}

export interface WorkflowStepRecord {
  id: string;
  workflowRunId: string;
  stepName: string;
  skillName: string;
  sequenceOrder: number;
  status: WorkflowStepStatus;
  dependsOnSteps: string[];
  requiredArtifactTypes: string[];
  producedArtifactTypes: string[];
  stepPayload: Record<string, unknown>;
  latestJobId: string | null;
  attemptCount: number;
  startedAt: Date | null;
  finishedAt: Date | null;
  lastError: string | null;
  createdAt: Date;
  updatedAt: Date;
}

export interface ArtifactRecord {
  id: string;
  requirementId: string;
  workflowRunId: string | null;
  workflowStepId: string | null;
  jobId: string | null;
  artifactType: string;
  relativePath: string;
  mimeType: string | null;
  sizeBytes: number | null;
  checksum: string | null;
  metadata: Record<string, unknown>;
  createdAt: Date;
}

export interface WorkflowLaunchResult {
  requirement: RequirementRecord;
  workflowRun: WorkflowRunRecord;
  workflowSteps: WorkflowStepRecord[];
  firstJob: JobRecord;
}

export function serializeRequirement(requirement: RequirementRecord) {
  return {
    id: requirement.id,
    requirementCode: requirement.requirementCode,
    caseName: requirement.caseName,
    notifyEmail: requirement.notifyEmail,
    rootDir: requirement.rootDir,
    status: requirement.status,
    inputPayload: requirement.inputPayload,
    createdAt: requirement.createdAt.toISOString(),
    updatedAt: requirement.updatedAt.toISOString(),
  };
}

export function serializeWorkflowRun(workflowRun: WorkflowRunRecord) {
  return {
    id: workflowRun.id,
    requirementId: workflowRun.requirementId,
    workflowName: workflowRun.workflowName,
    executionMode: workflowRun.executionMode,
    status: workflowRun.status,
    currentStepName: workflowRun.currentStepName,
    notifyOnCompletion: workflowRun.notifyOnCompletion,
    inputPayload: workflowRun.inputPayload,
    startedAt: workflowRun.startedAt?.toISOString() ?? null,
    finishedAt: workflowRun.finishedAt?.toISOString() ?? null,
    lastError: workflowRun.lastError,
    createdAt: workflowRun.createdAt.toISOString(),
    updatedAt: workflowRun.updatedAt.toISOString(),
  };
}

export function serializeWorkflowStep(workflowStep: WorkflowStepRecord) {
  return {
    id: workflowStep.id,
    workflowRunId: workflowStep.workflowRunId,
    stepName: workflowStep.stepName,
    skillName: workflowStep.skillName,
    sequenceOrder: workflowStep.sequenceOrder,
    status: workflowStep.status,
    dependsOnSteps: workflowStep.dependsOnSteps,
    requiredArtifactTypes: workflowStep.requiredArtifactTypes,
    producedArtifactTypes: workflowStep.producedArtifactTypes,
    stepPayload: workflowStep.stepPayload,
    latestJobId: workflowStep.latestJobId,
    attemptCount: workflowStep.attemptCount,
    startedAt: workflowStep.startedAt?.toISOString() ?? null,
    finishedAt: workflowStep.finishedAt?.toISOString() ?? null,
    lastError: workflowStep.lastError,
    createdAt: workflowStep.createdAt.toISOString(),
    updatedAt: workflowStep.updatedAt.toISOString(),
  };
}

export function serializeWorkflowLaunchResult(result: WorkflowLaunchResult) {
  return {
    requirement: serializeRequirement(result.requirement),
    workflowRun: serializeWorkflowRun(result.workflowRun),
    workflowSteps: result.workflowSteps.map(serializeWorkflowStep),
    firstJob: serializeJob(result.firstJob),
  };
}
