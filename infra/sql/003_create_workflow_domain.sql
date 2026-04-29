CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'execution_mode') THEN
    CREATE TYPE execution_mode AS ENUM ('standalone', 'workflow');
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'requirement_status') THEN
    CREATE TYPE requirement_status AS ENUM (
      'CREATED',
      'RUNNING',
      'COMPLETED',
      'FAILED',
      'PARTIAL'
    );
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'workflow_run_status') THEN
    CREATE TYPE workflow_run_status AS ENUM (
      'CREATED',
      'RUNNING',
      'COMPLETED',
      'FAILED',
      'CANCELLED'
    );
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'workflow_step_status') THEN
    CREATE TYPE workflow_step_status AS ENUM (
      'PENDING',
      'READY',
      'ENQUEUED',
      'RUNNING',
      'COMPLETED',
      'FAILED',
      'BLOCKED',
      'SKIPPED'
    );
  END IF;
END $$;

CREATE SEQUENCE IF NOT EXISTS requirement_code_seq
  START WITH 1
  INCREMENT BY 1;

CREATE OR REPLACE FUNCTION generate_requirement_code()
RETURNS TEXT AS $$
BEGIN
  RETURN 'REQ-' || LPAD(nextval('requirement_code_seq')::text, 6, '0');
END;
$$ LANGUAGE plpgsql;

CREATE TABLE IF NOT EXISTS requirements (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  requirement_code TEXT NOT NULL UNIQUE DEFAULT generate_requirement_code(),
  case_name TEXT,
  notify_email TEXT NOT NULL,
  root_dir TEXT NOT NULL,
  status requirement_status NOT NULL DEFAULT 'CREATED',
  input_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS workflow_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  requirement_id UUID NOT NULL REFERENCES requirements(id) ON DELETE CASCADE,
  workflow_name TEXT NOT NULL,
  execution_mode execution_mode NOT NULL DEFAULT 'standalone',
  status workflow_run_status NOT NULL DEFAULT 'CREATED',
  current_step_name TEXT,
  notify_on_completion BOOLEAN NOT NULL DEFAULT TRUE,
  input_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  last_error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS workflow_steps (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workflow_run_id UUID NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
  step_name TEXT NOT NULL,
  skill_name TEXT NOT NULL,
  sequence_order INTEGER NOT NULL CHECK (sequence_order >= 0),
  status workflow_step_status NOT NULL DEFAULT 'PENDING',
  depends_on_steps JSONB NOT NULL DEFAULT '[]'::jsonb,
  required_artifact_types JSONB NOT NULL DEFAULT '[]'::jsonb,
  produced_artifact_types JSONB NOT NULL DEFAULT '[]'::jsonb,
  step_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  latest_job_id UUID,
  attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  last_error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_workflow_steps_name UNIQUE (workflow_run_id, step_name),
  CONSTRAINT uq_workflow_steps_order UNIQUE (workflow_run_id, sequence_order)
);

CREATE TABLE IF NOT EXISTS artifacts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  requirement_id UUID NOT NULL REFERENCES requirements(id) ON DELETE CASCADE,
  workflow_run_id UUID REFERENCES workflow_runs(id) ON DELETE CASCADE,
  workflow_step_id UUID REFERENCES workflow_steps(id) ON DELETE CASCADE,
  job_id UUID REFERENCES jobs(id) ON DELETE SET NULL,
  artifact_type TEXT NOT NULL,
  relative_path TEXT NOT NULL,
  mime_type TEXT,
  size_bytes BIGINT,
  checksum TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_artifacts_requirement_path UNIQUE (requirement_id, relative_path)
);

ALTER TABLE jobs
  ADD COLUMN IF NOT EXISTS requirement_uuid UUID,
  ADD COLUMN IF NOT EXISTS workflow_run_id UUID,
  ADD COLUMN IF NOT EXISTS workflow_step_id UUID,
  ADD COLUMN IF NOT EXISTS output_dir TEXT;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'fk_jobs_requirement_uuid'
  ) THEN
    ALTER TABLE jobs
      ADD CONSTRAINT fk_jobs_requirement_uuid
      FOREIGN KEY (requirement_uuid) REFERENCES requirements(id) ON DELETE SET NULL;
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'fk_jobs_workflow_run_id'
  ) THEN
    ALTER TABLE jobs
      ADD CONSTRAINT fk_jobs_workflow_run_id
      FOREIGN KEY (workflow_run_id) REFERENCES workflow_runs(id) ON DELETE SET NULL;
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'fk_jobs_workflow_step_id'
  ) THEN
    ALTER TABLE jobs
      ADD CONSTRAINT fk_jobs_workflow_step_id
      FOREIGN KEY (workflow_step_id) REFERENCES workflow_steps(id) ON DELETE SET NULL;
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'fk_workflow_steps_latest_job_id'
  ) THEN
    ALTER TABLE workflow_steps
      ADD CONSTRAINT fk_workflow_steps_latest_job_id
      FOREIGN KEY (latest_job_id) REFERENCES jobs(id) ON DELETE SET NULL;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_requirements_code
  ON requirements (requirement_code);

CREATE INDEX IF NOT EXISTS idx_requirements_status_created_at
  ON requirements (status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_workflow_runs_requirement_id_created_at
  ON workflow_runs (requirement_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_workflow_runs_status_created_at
  ON workflow_runs (status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_workflow_steps_workflow_run_order
  ON workflow_steps (workflow_run_id, sequence_order);

CREATE INDEX IF NOT EXISTS idx_workflow_steps_status_created_at
  ON workflow_steps (status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_artifacts_requirement_created_at
  ON artifacts (requirement_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_artifacts_job_id
  ON artifacts (job_id);

CREATE INDEX IF NOT EXISTS idx_jobs_requirement_uuid_created_at
  ON jobs (requirement_uuid, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_jobs_workflow_run_id_created_at
  ON jobs (workflow_run_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_jobs_workflow_step_id_created_at
  ON jobs (workflow_step_id, created_at DESC);

DROP TRIGGER IF EXISTS requirements_set_updated_at ON requirements;
CREATE TRIGGER requirements_set_updated_at
BEFORE UPDATE ON requirements
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS workflow_runs_set_updated_at ON workflow_runs;
CREATE TRIGGER workflow_runs_set_updated_at
BEFORE UPDATE ON workflow_runs
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS workflow_steps_set_updated_at ON workflow_steps;
CREATE TRIGGER workflow_steps_set_updated_at
BEFORE UPDATE ON workflow_steps
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_name = 'jobs'
      AND column_name = 'parent_job_id'
  ) THEN
    COMMENT ON COLUMN jobs.parent_job_id IS
      'Deprecated for orchestration. Keep only as temporary compatibility metadata while the system migrates to requirement/workflow_run/workflow_step.';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_name = 'jobs'
      AND column_name = 'requirement_id'
  ) THEN
    COMMENT ON COLUMN jobs.requirement_id IS
      'Legacy requirement code string. The normalized relation should move to jobs.requirement_uuid -> requirements.id.';
  END IF;
END $$;
