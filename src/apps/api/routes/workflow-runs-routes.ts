import { Router } from "express";
import { ZodError } from "zod";

import {
  createWorkflowRunRequestSchema,
  serializeWorkflowLaunchResult,
} from "../../../shared/workflows/workflow-types.js";
import {
  QueuePublishError,
  UnsupportedSkillError,
} from "../services/workflow-launch-service.js";
import { WorkflowRunsService } from "../services/workflow-runs-service.js";
import {
  UnknownWorkflowError,
  UnsupportedWorkflowSkillError,
} from "../../../shared/workflows/workflow-definitions.js";

export function createWorkflowRunsRouter(workflowRunsService: WorkflowRunsService) {
  const router = Router();

  router.post("/", async (request, response, next) => {
    try {
      const payload = createWorkflowRunRequestSchema.parse(request.body);
      const result = await workflowRunsService.createAndLaunchWorkflowRun(payload);

      response.status(202).json({
        data: serializeWorkflowLaunchResult(result),
      });
    } catch (error) {
      if (error instanceof ZodError) {
        response.status(400).json({
          error: "Invalid workflow-run payload",
          details: error.flatten(),
        });
        return;
      }

      if (
        error instanceof UnknownWorkflowError ||
        error instanceof UnsupportedWorkflowSkillError ||
        error instanceof UnsupportedSkillError
      ) {
        response.status(400).json({
          error: error.message,
        });
        return;
      }

      if (error instanceof QueuePublishError) {
        response.status(503).json({
          error: error.message,
        });
        return;
      }

      next(error);
    }
  });

  return router;
}
