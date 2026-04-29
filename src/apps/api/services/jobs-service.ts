import { JobsRepository } from "../../../shared/db/jobs-repository.js";
import {
  type CreateJobRequest,
} from "../../../shared/jobs/job-types.js";
import type { WorkflowLaunchService } from "./workflow-launch-service.js";

export class JobNotFoundError extends Error {
  constructor(jobId: string) {
    super(`Job ${jobId} was not found.`);
    this.name = "JobNotFoundError";
  }
}

export class JobsService {
  constructor(
    private readonly jobsRepository: JobsRepository,
    private readonly workflowLaunchService: WorkflowLaunchService,
  ) {}

  async createAndEnqueueJob(input: CreateJobRequest) {
    const launch = await this.workflowLaunchService.launchStandalone(input);
    return launch.firstJob;
  }

  async getJob(jobId: string) {
    const job = await this.jobsRepository.findById(jobId);

    if (!job) {
      throw new JobNotFoundError(jobId);
    }

    return job;
  }
}
