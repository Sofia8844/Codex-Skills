import { stat } from "node:fs/promises";
import { relative, resolve } from "node:path";
import type { QueryResultRow } from "pg";

import type { ExecutionMode } from "../jobs/job-types.js";
import type {
  ArtifactRecord,
  RequirementRecord,
  RequirementStatus,
  WorkflowRunRecord,
  WorkflowRunStatus,
  WorkflowStepRecord,
  WorkflowStepStatus,
} from "../workflows/workflow-types.js";
import { query, type DatabaseExecutor } from "./postgres.js";

interface RequirementRow extends QueryResultRow {
  id: string;
  requirement_code: string;
  case_name: string | null;
  notify_email: string;
  root_dir: string;
  status: RequirementStatus;
  input_payload: Record<string, unknown>;
  created_at: Date | string;
  updated_at: Date | string;
}

interface WorkflowRunRow extends QueryResultRow {
  id: string;
  requirement_id: string;
  workflow_name: string;
  execution_mode: ExecutionMode;
  status: WorkflowRunStatus;
  current_step_name: string | null;
  notify_on_completion: boolean;
  input_payload: Record<string, unknown>;
  started_at: Date | string | null;
  finished_at: Date | string | null;
  last_error: string | null;
  created_at: Date | string;
  updated_at: Date | string;
}

interface WorkflowStepRow extends QueryResultRow {
  id: string;
  workflow_run_id: string;
  step_name: string;
  skill_name: string;
  sequence_order: number;
  status: WorkflowStepStatus;
  depends_on_steps: string[];
  required_artifact_types: string[];
  produced_artifact_types: string[];
  step_payload: Record<string, unknown>;
  latest_job_id: string | null;
  attempt_count: number;
  started_at: Date | string | null;
  finished_at: Date | string | null;
  last_error: string | null;
  created_at: Date | string;
  updated_at: Date | string;
}

interface ArtifactRow extends QueryResultRow {
  id: string;
  requirement_id: string;
  workflow_run_id: string | null;
  workflow_step_id: string | null;
  job_id: string | null;
  artifact_type: string;
  relative_path: string;
  mime_type: string | null;
  size_bytes: number | null;
  checksum: string | null;
  metadata: Record<string, unknown>;
  created_at: Date | string;
}

const defaultExecutor: DatabaseExecutor = { query };

function getExecutor(executor?: DatabaseExecutor) {
  return executor ?? defaultExecutor;
}

function toDate(value: Date | string | null) {
  if (!value) {
    return null;
  }

  return value instanceof Date ? value : new Date(value);
}

function requireRow<T>(row: T | undefined, operation: string) {
  if (!row) {
    throw new Error(`Database operation "${operation}" did not return a row.`);
  }

  return row;
}

function mapRequirementRow(row: RequirementRow): RequirementRecord {
  return {
    id: row.id,
    requirementCode: row.requirement_code,
    caseName: row.case_name,
    notifyEmail: row.notify_email,
    rootDir: row.root_dir,
    status: row.status,
    inputPayload: row.input_payload,
    createdAt: toDate(row.created_at) ?? new Date(),
    updatedAt: toDate(row.updated_at) ?? new Date(),
  };
}

function mapWorkflowRunRow(row: WorkflowRunRow): WorkflowRunRecord {
  return {
    id: row.id,
    requirementId: row.requirement_id,
    workflowName: row.workflow_name,
    executionMode: row.execution_mode,
    status: row.status,
    currentStepName: row.current_step_name,
    notifyOnCompletion: row.notify_on_completion,
    inputPayload: row.input_payload,
    startedAt: toDate(row.started_at),
    finishedAt: toDate(row.finished_at),
    lastError: row.last_error,
    createdAt: toDate(row.created_at) ?? new Date(),
    updatedAt: toDate(row.updated_at) ?? new Date(),
  };
}

function mapWorkflowStepRow(row: WorkflowStepRow): WorkflowStepRecord {
  return {
    id: row.id,
    workflowRunId: row.workflow_run_id,
    stepName: row.step_name,
    skillName: row.skill_name,
    sequenceOrder: row.sequence_order,
    status: row.status,
    dependsOnSteps: row.depends_on_steps,
    requiredArtifactTypes: row.required_artifact_types,
    producedArtifactTypes: row.produced_artifact_types,
    stepPayload: row.step_payload,
    latestJobId: row.latest_job_id,
    attemptCount: row.attempt_count,
    startedAt: toDate(row.started_at),
    finishedAt: toDate(row.finished_at),
    lastError: row.last_error,
    createdAt: toDate(row.created_at) ?? new Date(),
    updatedAt: toDate(row.updated_at) ?? new Date(),
  };
}

function mapArtifactRow(row: ArtifactRow): ArtifactRecord {
  return {
    id: row.id,
    requirementId: row.requirement_id,
    workflowRunId: row.workflow_run_id,
    workflowStepId: row.workflow_step_id,
    jobId: row.job_id,
    artifactType: row.artifact_type,
    relativePath: row.relative_path,
    mimeType: row.mime_type,
    sizeBytes: row.size_bytes,
    checksum: row.checksum,
    metadata: row.metadata,
    createdAt: toDate(row.created_at) ?? new Date(),
  };
}

export class RequirementsRepository {
  async reserveRequirementCode(executor?: DatabaseExecutor) {
    const result = await getExecutor(executor).query<{ requirement_code: string }>(
      "SELECT generate_requirement_code() AS requirement_code",
    );

    return requireRow(result.rows[0], "reserveRequirementCode").requirement_code;
  }

  async create(
    input: {
      requirementCode: string;
      caseName?: string;
      notifyEmail: string;
      rootDir: string;
      inputPayload: Record<string, unknown>;
      status?: RequirementStatus;
    },
    executor?: DatabaseExecutor,
  ) {
    const result = await getExecutor(executor).query<RequirementRow>(
      `
        INSERT INTO requirements (
          requirement_code,
          case_name,
          notify_email,
          root_dir,
          status,
          input_payload
        )
        VALUES ($1, $2, $3, $4, $5, $6::jsonb)
        RETURNING *
      `,
      [
        input.requirementCode,
        input.caseName ?? null,
        input.notifyEmail,
        input.rootDir,
        input.status ?? "CREATED",
        JSON.stringify(input.inputPayload),
      ],
    );

    return mapRequirementRow(requireRow(result.rows[0], "createRequirement"));
  }

  async markStatus(id: string, status: RequirementStatus, executor?: DatabaseExecutor) {
    const result = await getExecutor(executor).query<RequirementRow>(
      `
        UPDATE requirements
        SET status = $2
        WHERE id = $1
        RETURNING *
      `,
      [id, status],
    );

    return mapRequirementRow(requireRow(result.rows[0], "markRequirementStatus"));
  }

  async findById(id: string, executor?: DatabaseExecutor) {
    const result = await getExecutor(executor).query<RequirementRow>(
      "SELECT * FROM requirements WHERE id = $1",
      [id],
    );

    if (result.rows.length === 0) {
      return null;
    }

    return mapRequirementRow(requireRow(result.rows[0], "findRequirementById"));
  }
}

export class WorkflowRunsRepository {
  async create(
    input: {
      requirementId: string;
      workflowName: string;
      executionMode: ExecutionMode;
      inputPayload: Record<string, unknown>;
      status?: WorkflowRunStatus;
      currentStepName?: string;
      notifyOnCompletion?: boolean;
    },
    executor?: DatabaseExecutor,
  ) {
    const result = await getExecutor(executor).query<WorkflowRunRow>(
      `
        INSERT INTO workflow_runs (
          requirement_id,
          workflow_name,
          execution_mode,
          status,
          current_step_name,
          notify_on_completion,
          input_payload
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
        RETURNING *
      `,
      [
        input.requirementId,
        input.workflowName,
        input.executionMode,
        input.status ?? "CREATED",
        input.currentStepName ?? null,
        input.notifyOnCompletion ?? true,
        JSON.stringify(input.inputPayload),
      ],
    );

    return mapWorkflowRunRow(requireRow(result.rows[0], "createWorkflowRun"));
  }

  async markRunning(id: string, currentStepName: string, executor?: DatabaseExecutor) {
    const result = await getExecutor(executor).query<WorkflowRunRow>(
      `
        UPDATE workflow_runs
        SET
          status = 'RUNNING',
          current_step_name = $2,
          started_at = COALESCE(started_at, NOW()),
          last_error = NULL
        WHERE id = $1
        RETURNING *
      `,
      [id, currentStepName],
    );

    return mapWorkflowRunRow(requireRow(result.rows[0], "markWorkflowRunRunning"));
  }

  async markFailed(id: string, errorMessage: string, executor?: DatabaseExecutor) {
    const result = await getExecutor(executor).query<WorkflowRunRow>(
      `
        UPDATE workflow_runs
        SET
          status = 'FAILED',
          last_error = $2,
          finished_at = NOW()
        WHERE id = $1
        RETURNING *
      `,
      [id, errorMessage],
    );

    return mapWorkflowRunRow(requireRow(result.rows[0], "markWorkflowRunFailed"));
  }

  async markCompleted(id: string, executor?: DatabaseExecutor) {
    const result = await getExecutor(executor).query<WorkflowRunRow>(
      `
        UPDATE workflow_runs
        SET
          status = 'COMPLETED',
          current_step_name = NULL,
          last_error = NULL,
          finished_at = NOW()
        WHERE id = $1
        RETURNING *
      `,
      [id],
    );

    return mapWorkflowRunRow(requireRow(result.rows[0], "markWorkflowRunCompleted"));
  }

  async findById(id: string, executor?: DatabaseExecutor) {
    const result = await getExecutor(executor).query<WorkflowRunRow>(
      "SELECT * FROM workflow_runs WHERE id = $1",
      [id],
    );

    if (result.rows.length === 0) {
      return null;
    }

    return mapWorkflowRunRow(requireRow(result.rows[0], "findWorkflowRunById"));
  }
}

export class WorkflowStepsRepository {
  async createMany(
    steps: Array<{
      workflowRunId: string;
      stepName: string;
      skillName: string;
      sequenceOrder: number;
      status?: WorkflowStepStatus;
      dependsOnSteps?: string[];
      requiredArtifactTypes?: string[];
      producedArtifactTypes?: string[];
      stepPayload?: Record<string, unknown>;
    }>,
    executor?: DatabaseExecutor,
  ) {
    const db = getExecutor(executor);
    const created: WorkflowStepRecord[] = [];

    for (const step of steps) {
      const result = await db.query<WorkflowStepRow>(
        `
          INSERT INTO workflow_steps (
            workflow_run_id,
            step_name,
            skill_name,
            sequence_order,
            status,
            depends_on_steps,
            required_artifact_types,
            produced_artifact_types,
            step_payload
          )
          VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, $8::jsonb, $9::jsonb)
          RETURNING *
        `,
        [
          step.workflowRunId,
          step.stepName,
          step.skillName,
          step.sequenceOrder,
          step.status ?? "PENDING",
          JSON.stringify(step.dependsOnSteps ?? []),
          JSON.stringify(step.requiredArtifactTypes ?? []),
          JSON.stringify(step.producedArtifactTypes ?? []),
          JSON.stringify(step.stepPayload ?? {}),
        ],
      );

      created.push(mapWorkflowStepRow(requireRow(result.rows[0], "createWorkflowStep")));
    }

    return created;
  }

  async markEnqueued(id: string, latestJobId: string, executor?: DatabaseExecutor) {
    const result = await getExecutor(executor).query<WorkflowStepRow>(
      `
        UPDATE workflow_steps
        SET
          status = 'ENQUEUED',
          latest_job_id = $2,
          last_error = NULL
        WHERE id = $1
        RETURNING *
      `,
      [id, latestJobId],
    );

    return mapWorkflowStepRow(requireRow(result.rows[0], "markWorkflowStepEnqueued"));
  }

  async markReady(
    id: string,
    latestJobId?: string,
    executor?: DatabaseExecutor,
  ) {
    const result = await getExecutor(executor).query<WorkflowStepRow>(
      `
        UPDATE workflow_steps
        SET
          status = 'READY',
          latest_job_id = COALESCE($2, latest_job_id),
          last_error = NULL
        WHERE id = $1
        RETURNING *
      `,
      [id, latestJobId ?? null],
    );

    return mapWorkflowStepRow(requireRow(result.rows[0], "markWorkflowStepReady"));
  }

  async markRunning(id: string, latestJobId: string, executor?: DatabaseExecutor) {
    const result = await getExecutor(executor).query<WorkflowStepRow>(
      `
        UPDATE workflow_steps
        SET
          status = 'RUNNING',
          latest_job_id = $2,
          attempt_count = attempt_count + 1,
          started_at = COALESCE(started_at, NOW()),
          finished_at = NULL,
          last_error = NULL
        WHERE id = $1
        RETURNING *
      `,
      [id, latestJobId],
    );

    return mapWorkflowStepRow(requireRow(result.rows[0], "markWorkflowStepRunning"));
  }

  async markCompleted(id: string, latestJobId: string, executor?: DatabaseExecutor) {
    const result = await getExecutor(executor).query<WorkflowStepRow>(
      `
        UPDATE workflow_steps
        SET
          status = 'COMPLETED',
          latest_job_id = $2,
          last_error = NULL,
          finished_at = NOW()
        WHERE id = $1
        RETURNING *
      `,
      [id, latestJobId],
    );

    return mapWorkflowStepRow(requireRow(result.rows[0], "markWorkflowStepCompleted"));
  }

  async markFailed(
    id: string,
    errorMessage: string,
    latestJobId?: string,
    executor?: DatabaseExecutor,
  ) {
    const result = await getExecutor(executor).query<WorkflowStepRow>(
      `
        UPDATE workflow_steps
        SET
          status = 'FAILED',
          latest_job_id = COALESCE($2, latest_job_id),
          last_error = $3,
          finished_at = NOW()
        WHERE id = $1
        RETURNING *
      `,
      [id, latestJobId ?? null, errorMessage],
    );

    return mapWorkflowStepRow(requireRow(result.rows[0], "markWorkflowStepFailed"));
  }

  async findById(id: string, executor?: DatabaseExecutor) {
    const result = await getExecutor(executor).query<WorkflowStepRow>(
      "SELECT * FROM workflow_steps WHERE id = $1",
      [id],
    );

    if (result.rows.length === 0) {
      return null;
    }

    return mapWorkflowStepRow(requireRow(result.rows[0], "findWorkflowStepById"));
  }

  async listByWorkflowRunId(workflowRunId: string, executor?: DatabaseExecutor) {
    const result = await getExecutor(executor).query<WorkflowStepRow>(
      `
        SELECT *
        FROM workflow_steps
        WHERE workflow_run_id = $1
        ORDER BY sequence_order ASC
      `,
      [workflowRunId],
    );

    return result.rows.map(mapWorkflowStepRow);
  }
}

export class ArtifactsRepository {
  async upsertByAbsolutePath(
    input: {
      requirementId: string;
      workflowRunId?: string | null;
      workflowStepId?: string | null;
      jobId?: string | null;
      rootDir: string;
      artifactType: string;
      absolutePath: string;
      metadata?: Record<string, unknown>;
    },
    executor?: DatabaseExecutor,
  ) {
    const resolvedRootDir = resolve(input.rootDir);
    const resolvedArtifactPath = resolve(input.absolutePath);
    const fileStat = await stat(resolvedArtifactPath);
    const relativePath = relative(resolvedRootDir, resolvedArtifactPath).replaceAll("\\", "/");

    const result = await getExecutor(executor).query<ArtifactRow>(
      `
        INSERT INTO artifacts (
          requirement_id,
          workflow_run_id,
          workflow_step_id,
          job_id,
          artifact_type,
          relative_path,
          size_bytes,
          metadata
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
        ON CONFLICT (requirement_id, relative_path)
        DO UPDATE
        SET
          workflow_run_id = EXCLUDED.workflow_run_id,
          workflow_step_id = EXCLUDED.workflow_step_id,
          job_id = EXCLUDED.job_id,
          artifact_type = EXCLUDED.artifact_type,
          size_bytes = EXCLUDED.size_bytes,
          metadata = EXCLUDED.metadata
        RETURNING *
      `,
      [
        input.requirementId,
        input.workflowRunId ?? null,
        input.workflowStepId ?? null,
        input.jobId ?? null,
        input.artifactType,
        relativePath,
        Number(fileStat.size),
        JSON.stringify(input.metadata ?? {}),
      ],
    );

    return mapArtifactRow(requireRow(result.rows[0], "upsertArtifactByAbsolutePath"));
  }

  async listByWorkflowRunId(workflowRunId: string, executor?: DatabaseExecutor) {
    const result = await getExecutor(executor).query<ArtifactRow>(
      `
        SELECT *
        FROM artifacts
        WHERE workflow_run_id = $1
        ORDER BY created_at ASC
      `,
      [workflowRunId],
    );

    return result.rows.map(mapArtifactRow);
  }
}
