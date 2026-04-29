import { isRegisteredSkill } from "../jobs/skill-registry.js";

export interface WorkflowStepDefinition {
  stepName: string;
  skillName: string;
  sequenceOrder: number;
  dependsOnSteps: string[];
  requiredArtifactTypes: string[];
  producedArtifactTypes: string[];
}

export interface WorkflowDefinition {
  workflowName: string;
  executionMode: "workflow";
  steps: WorkflowStepDefinition[];
}

export class UnknownWorkflowError extends Error {
  constructor(workflowName: string) {
    super(`Workflow "${workflowName}" is not defined.`);
    this.name = "UnknownWorkflowError";
  }
}

export class UnsupportedWorkflowSkillError extends Error {
  constructor(workflowName: string, skillName: string) {
    super(
      `Workflow "${workflowName}" uses skill "${skillName}", but that skill is not registered in the worker.`,
    );
    this.name = "UnsupportedWorkflowSkillError";
  }
}

const definitions = new Map<string, WorkflowDefinition>([
  [
    "network_pipeline_v1",
    {
      workflowName: "network_pipeline_v1",
      executionMode: "workflow",
      steps: [
        {
          stepName: "design",
          skillName: "diseno-redes-empresariales",
          sequenceOrder: 0,
          dependsOnSteps: [],
          requiredArtifactTypes: ["request_input"],
          producedArtifactTypes: [
            "design_handoff",
            "design_explanation_md",
            "design_explanation_pdf",
          ],
        },
        {
          stepName: "quote",
          skillName: "cotizacion-redes-empresariales",
          sequenceOrder: 1,
          dependsOnSteps: ["design"],
          requiredArtifactTypes: ["design_handoff"],
          producedArtifactTypes: [
            "quote_output",
            "quote_explanation_md",
            "quote_explanation_pdf",
          ],
        },
        {
          stepName: "proposal",
          skillName: "creacion-propuesta",
          sequenceOrder: 2,
          dependsOnSteps: ["design", "quote"],
          requiredArtifactTypes: ["design_handoff", "quote_output"],
          producedArtifactTypes: [
            "proposal_context",
            "proposal_spec",
            "proposal_pptx",
          ],
        },
      ],
    },
  ],
]);

export function listWorkflowDefinitions() {
  return [...definitions.keys()];
}

export function getWorkflowDefinition(workflowName: string) {
  const definition = definitions.get(workflowName);

  if (!definition) {
    throw new UnknownWorkflowError(workflowName);
  }

  return definition;
}

export function assertWorkflowSkillsRegistered(workflowName: string) {
  const definition = getWorkflowDefinition(workflowName);

  for (const step of definition.steps) {
    if (!isRegisteredSkill(step.skillName)) {
      throw new UnsupportedWorkflowSkillError(workflowName, step.skillName);
    }
  }

  return definition;
}
