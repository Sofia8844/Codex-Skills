CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'job_status') THEN
    CREATE TYPE job_status AS ENUM ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED');
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'notification_status') THEN
    CREATE TYPE notification_status AS ENUM ('PENDING', 'QUEUED', 'SENT', 'FAILED');
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  skill_name TEXT NOT NULL,
  status job_status NOT NULL DEFAULT 'PENDING',
  notification_email TEXT NOT NULL,
  notification_status notification_status NOT NULL DEFAULT 'PENDING',
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  stdout TEXT,
  stderr TEXT,
  error_message TEXT,
  output_file TEXT,
  exit_code INTEGER,
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  notification_queued_at TIMESTAMPTZ,
  notification_sent_at TIMESTAMPTZ,
  notification_error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_jobs_status_created_at
  ON jobs (status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_jobs_skill_name_created_at
  ON jobs (skill_name, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_jobs_notification_status
  ON jobs (notification_status, created_at DESC);

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS jobs_set_updated_at ON jobs;

CREATE TRIGGER jobs_set_updated_at
BEFORE UPDATE ON jobs
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();
