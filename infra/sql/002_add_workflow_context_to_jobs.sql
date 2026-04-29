DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'execution_mode') THEN
    CREATE TYPE execution_mode AS ENUM ('standalone', 'workflow');
  END IF;
END $$;

ALTER TABLE jobs
  ADD COLUMN IF NOT EXISTS requirement_id TEXT,
  ADD COLUMN IF NOT EXISTS execution_mode execution_mode NOT NULL DEFAULT 'standalone',
  ADD COLUMN IF NOT EXISTS workflow_name TEXT,
  ADD COLUMN IF NOT EXISTS step_name TEXT,
  ADD COLUMN IF NOT EXISTS parent_job_id UUID REFERENCES jobs(id),
  ADD COLUMN IF NOT EXISTS case_root_dir TEXT;

CREATE INDEX IF NOT EXISTS idx_jobs_requirement_id_created_at
  ON jobs (requirement_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_jobs_execution_mode_created_at
  ON jobs (execution_mode, created_at DESC);
