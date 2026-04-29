import { Router } from "express";
import { ZodError } from "zod";

import {
  createJobRequestSchema,
  jobIdParamsSchema,
  serializeJob,
} from "../../../shared/jobs/job-types.js";
import {
  JobNotFoundError,
  JobsService,
} from "../services/jobs-service.js";
import {
  QueuePublishError,
  UnsupportedSkillError,
} from "../services/workflow-launch-service.js";

export function createJobsRouter(jobsService: JobsService) {
  const router = Router();

  router.post("/", async (request, response, next) => {
    try {
      const payload = createJobRequestSchema.parse(request.body);
      const job = await jobsService.createAndEnqueueJob(payload);

      response.status(202).json({
        data: serializeJob(job),
      });
    } catch (error) {
      if (error instanceof ZodError) {
        response.status(400).json({
          error: "Invalid request payload",
          details: error.flatten(),
        });
        return;
      }

      if (error instanceof UnsupportedSkillError) {
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

  router.get("/:id", async (request, response, next) => {
    try {
      const { id } = jobIdParamsSchema.parse(request.params);
      const job = await jobsService.getJob(id);

      response.status(200).json({
        data: serializeJob(job),
      });
    } catch (error) {
      if (error instanceof ZodError) {
        response.status(400).json({
          error: "Invalid job id",
          details: error.flatten(),
        });
        return;
      }

      if (error instanceof JobNotFoundError) {
        response.status(404).json({
          error: error.message,
        });
        return;
      }

      next(error);
    }
  });

  return router;
}
