import type { CreateWorkflowRunRequest } from "../../../shared/workflows/workflow-types.js";
import type { WorkflowLaunchService } from "./workflow-launch-service.js";

export class WorkflowRunsService {
  constructor(private readonly workflowLaunchService: WorkflowLaunchService) {}

  async createAndLaunchWorkflowRun(input: CreateWorkflowRunRequest) {
    return this.workflowLaunchService.launchWorkflowRun(input);
  }
}
