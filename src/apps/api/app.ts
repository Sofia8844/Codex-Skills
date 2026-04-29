import express from "express";

import { createLogger } from "../../shared/logging/logger.js";
import { createJobsRouter } from "./routes/jobs-routes.js";
import { createWorkflowRunsRouter } from "./routes/workflow-runs-routes.js";
import type { JobsService } from "./services/jobs-service.js";
import type { WorkflowRunsService } from "./services/workflow-runs-service.js";

const logger = createLogger("api:app");

export function createApp(
  jobsService: JobsService,
  workflowRunsService: WorkflowRunsService,
) {
  const app = express();

  app.use(express.json({ limit: "1mb" }));

  app.get("/health", (_request, response) => {
    response.status(200).json({
      status: "ok",
    });
  });

  app.use("/jobs", createJobsRouter(jobsService));
  app.use("/workflow-runs", createWorkflowRunsRouter(workflowRunsService));

  app.use(
    (
      error: unknown,
      _request: express.Request,
      response: express.Response,
      _next: express.NextFunction,
    ) => {
      logger.error("Unhandled API error", { error });

      response.status(500).json({
        error: "Internal server error",
      });
    },
  );

  return app;
}
