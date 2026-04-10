import type { ConfirmChannel } from "amqplib";

import { env } from "../../../shared/config/env.js";
import { JobsRepository } from "../../../shared/db/jobs-repository.js";
import {
  buildSkillJobMessage,
  type CreateJobRequest,
} from "../../../shared/jobs/job-types.js";
import {
  isRegisteredSkill,
  listAvailableSkills,
} from "../../../shared/jobs/skill-registry.js";
import { getErrorMessage } from "../../../shared/logging/logger.js";
import { publishJson } from "../../../shared/rabbitmq/rabbitmq.js";

export class JobNotFoundError extends Error {
  constructor(jobId: string) {
    super(`Job ${jobId} was not found.`);
    this.name = "JobNotFoundError";
  }
}

export class QueuePublishError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "QueuePublishError";
  }
}

export class UnsupportedSkillError extends Error {
  constructor(skillName: string) {
    super(
      `Skill "${skillName}" is not registered. Available skills: ${listAvailableSkills().join(", ")}`,
    );
    this.name = "UnsupportedSkillError";
  }
}

export class JobsService {
  constructor(
    private readonly jobsRepository: JobsRepository,
    private readonly publisherChannel: ConfirmChannel,
  ) {}

  async createAndEnqueueJob(input: CreateJobRequest) {
      // 1. Verifica que la skill existe
    if (!isRegisteredSkill(input.skillName)) {
      throw new UnsupportedSkillError(input.skillName);
    }
  // 2. Crea el job en DB con estado PENDING
    const job = await this.jobsRepository.createPendingJob({
      skillName: input.skillName,
      payload: input.payload,
      notificationEmail: input.notifyEmail,
    });
  // 3. Publica el mensaje en RabbitMQ
    try {
      await publishJson(
        this.publisherChannel,
        env.skillJobsQueue,
        buildSkillJobMessage(job),
      );
    } catch (error) {
      const message = `Unable to publish job ${job.id} to ${env.skillJobsQueue}: ${getErrorMessage(error)}`;
      await this.jobsRepository.markQueuePublishFailed(job.id, message);
      throw new QueuePublishError(message);
    }

    return job;
  }

  async getJob(jobId: string) {
    const job = await this.jobsRepository.findById(jobId);

    if (!job) {
      throw new JobNotFoundError(jobId);
    }

    return job;
  }
}
