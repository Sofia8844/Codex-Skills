# Workflow Orchestration Plan

## Target Model

The orchestration model now centers on:

- `requirements`: business case container (`REQ-000001`, folder, notify email, global state)
- `workflow_runs`: one execution flow over a requirement (`standalone`, `network_pipeline_v1`)
- `workflow_steps`: logical steps inside the flow (`design`, `quote`, `proposal`)
- `jobs`: operational execution attempts for a step
- `artifacts`: registered files produced by jobs and steps

## Why This Model

- A requirement is the real parent of the case, not a job.
- A workflow run owns the global progress and completion status.
- A workflow step owns dependencies and reruns.
- A job is only an execution attempt.

## Phase Order

1. Database foundation
   Create `requirements`, `workflow_runs`, `workflow_steps`, and `artifacts`.
   Add nullable foreign keys on `jobs` so migration can be rolled out without breaking current consumers.

2. API split
   Keep `POST /jobs` for standalone skill execution.
   Add `POST /workflow-runs` for orchestrated flows.

3. Worker integration
   When a job finishes, update its step, register artifacts, and reconcile the workflow.

4. Notification policy
   Send workflow-completion notifications from `workflow_runs` rather than per job by default.

5. Artifact-driven skills
   Resolve design, quote, and proposal inputs from the requirement folder and artifact registry.

## Database Notes

- Technical IDs should come from PostgreSQL (`UUID DEFAULT gen_random_uuid()`).
- The visible business identifier should come from PostgreSQL too (`requirements.requirement_code`).
- `jobs.parent_job_id` is now considered deprecated for orchestration design.
- `jobs.requirement_id` remains as a temporary legacy string until API and repositories are moved to `requirements.id`.
