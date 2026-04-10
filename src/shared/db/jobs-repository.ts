import type { QueryResultRow } from "pg";

import type { JobPayload, JobRecord } from "../jobs/job-types.js";
import { query } from "./postgres.js";

interface JobRow extends QueryResultRow {
  id: string;
  skill_name: string;
  status: JobRecord["status"];
  notification_email: string;
  notification_status: JobRecord["notificationStatus"];
  payload: JobPayload;
  attempts: number;
  stdout: string | null;
  stderr: string | null;
  error_message: string | null;
  output_file: string | null;
  exit_code: number | null;
  started_at: Date | string | null;
  finished_at: Date | string | null;
  notification_queued_at: Date | string | null;
  notification_sent_at: Date | string | null;
  notification_error: string | null;
  created_at: Date | string;
  updated_at: Date | string;
}

function toDate(value: Date | string | null) {
  if (!value) {
    return null;
  }

  return value instanceof Date ? value : new Date(value);
}

function mapRow(row: JobRow): JobRecord {
  return {
    id: row.id,
    skillName: row.skill_name,
    status: row.status,
    notificationEmail: row.notification_email,
    notificationStatus: row.notification_status,
    payload: row.payload,
    attempts: row.attempts,
    stdout: row.stdout,
    stderr: row.stderr,
    errorMessage: row.error_message,
    outputFile: row.output_file,
    exitCode: row.exit_code,
    startedAt: toDate(row.started_at),
    finishedAt: toDate(row.finished_at),
    notificationQueuedAt: toDate(row.notification_queued_at),
    notificationSentAt: toDate(row.notification_sent_at),
    notificationError: row.notification_error,
    createdAt: toDate(row.created_at) ?? new Date(),
    updatedAt: toDate(row.updated_at) ?? new Date(),
  };
}

function requireRow(row: JobRow | undefined, operation: string) {
  if (!row) {
    throw new Error(`Database operation "${operation}" did not return a row.`);
  }

  return row;
}

export class JobsRepository {
  async createPendingJob(input: {
    skillName: string;
    payload: JobPayload;
    notificationEmail: string;
  }) {
    const result = await query<JobRow>(
      `
        INSERT INTO jobs (skill_name, payload, notification_email, status, notification_status)
        VALUES ($1, $2::jsonb, $3, 'PENDING', 'PENDING')
        RETURNING *
      `,
      [input.skillName, JSON.stringify(input.payload), input.notificationEmail],
    );

    return mapRow(requireRow(result.rows[0], "createPendingJob"));
  }

  async findById(id: string) {
    const result = await query<JobRow>("SELECT * FROM jobs WHERE id = $1", [id]);

    if (result.rows.length === 0) {
      return null;
    }

    return mapRow(requireRow(result.rows[0], "findById"));
  }

  async markRunning(id: string) {
    const result = await query<JobRow>(
      `
        UPDATE jobs
        SET
          status = 'RUNNING',
          attempts = attempts + 1,
          started_at = NOW(),
          finished_at = NULL,
          stdout = NULL,
          stderr = NULL,
          error_message = NULL,
          exit_code = NULL
        WHERE id = $1
          AND status IN ('PENDING', 'RUNNING')
        RETURNING *
      `,
      [id],
    );

    if (result.rows.length === 0) {
      return null;
    }

    return mapRow(requireRow(result.rows[0], "markRunning"));
  }

  async markCompleted(
    id: string,
    resultData: {
      stdout: string | null;
      stderr: string | null;
      outputFile: string | null;
      exitCode: number | null;
    },
  ) {
    const result = await query<JobRow>(
      `
        UPDATE jobs
        SET
          status = 'COMPLETED',
          stdout = $2,
          stderr = $3,
          output_file = $4,
          exit_code = $5,
          error_message = NULL,
          finished_at = NOW()
        WHERE id = $1
        RETURNING *
      `,
      [id, resultData.stdout, resultData.stderr, resultData.outputFile, resultData.exitCode],
    );

    return mapRow(requireRow(result.rows[0], "markCompleted"));
  }

  async markFailed(
    id: string,
    resultData: {
      stdout: string | null;
      stderr: string | null;
      outputFile: string | null;
      exitCode: number | null;
      errorMessage: string;
    },
  ) {
    const result = await query<JobRow>(
      `
        UPDATE jobs
        SET
          status = 'FAILED',
          stdout = $2,
          stderr = $3,
          output_file = $4,
          exit_code = $5,
          error_message = $6,
          finished_at = NOW()
        WHERE id = $1
        RETURNING *
      `,
      [
        id,
        resultData.stdout,
        resultData.stderr,
        resultData.outputFile,
        resultData.exitCode,
        resultData.errorMessage,
      ],
    );

    return mapRow(requireRow(result.rows[0], "markFailed"));
  }

  async markQueuePublishFailed(id: string, errorMessage: string) {
    const result = await query<JobRow>(
      `
        UPDATE jobs
        SET
          status = 'FAILED',
          error_message = $2,
          finished_at = NOW()
        WHERE id = $1
        RETURNING *
      `,
      [id, errorMessage],
    );

    return mapRow(requireRow(result.rows[0], "markQueuePublishFailed"));
  }

  async markNotificationQueued(id: string) {
    const result = await query<JobRow>(
      `
        UPDATE jobs
        SET
          notification_status = 'QUEUED',
          notification_queued_at = NOW(),
          notification_error = NULL
        WHERE id = $1
        RETURNING *
      `,
      [id],
    );

    return mapRow(requireRow(result.rows[0], "markNotificationQueued"));
  }

  async markNotificationSent(id: string) {
    const result = await query<JobRow>(
      `
        UPDATE jobs
        SET
          notification_status = 'SENT',
          notification_sent_at = NOW(),
          notification_error = NULL
        WHERE id = $1
        RETURNING *
      `,
      [id],
    );

    return mapRow(requireRow(result.rows[0], "markNotificationSent"));
  }

  async markNotificationFailed(id: string, errorMessage: string) {
    const result = await query<JobRow>(
      `
        UPDATE jobs
        SET
          notification_status = 'FAILED',
          notification_error = $2
        WHERE id = $1
        RETURNING *
      `,
      [id, errorMessage],
    );

    return mapRow(requireRow(result.rows[0], "markNotificationFailed"));
  }
}
