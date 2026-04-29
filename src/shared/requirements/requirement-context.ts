import { randomBytes } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

export interface RequirementWorkspacePaths {
  caseRootDir: string;
  requestDir: string;
}

function slugifyStepName(value: string) {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "") || "step";
}

export function resolveRequirementWorkspace(
  projectRoot: string,
  requirementId: string,
): RequirementWorkspacePaths {
  const caseRootDir = resolve(projectRoot, "output", requirementId);
  const requestDir = resolve(caseRootDir, "request");

  return {
    caseRootDir,
    requestDir,
  };
}

function buildRequestSnapshotPath(requestDir: string, now = new Date()) {
  const timestamp = now.toISOString().replaceAll(":", "-");
  const suffix = randomBytes(2).toString("hex").toUpperCase();
  return resolve(requestDir, `${timestamp}-${suffix}-job-request.json`);
}

export async function ensureRequirementWorkspace(
  projectRoot: string,
  requirementId: string,
  requestSnapshot: unknown,
) {
  const paths = resolveRequirementWorkspace(projectRoot, requirementId);
  const requestSnapshotPath = buildRequestSnapshotPath(paths.requestDir);

  await mkdir(paths.requestDir, { recursive: true });
  await writeFile(
    requestSnapshotPath,
    `${JSON.stringify(requestSnapshot, null, 2)}\n`,
    "utf-8",
  );

  return {
    ...paths,
    requestSnapshotPath,
  };
}

export async function ensureWorkflowStepWorkspace(
  caseRootDir: string,
  stepName: string,
) {
  const stepOutputDir = resolve(caseRootDir, slugifyStepName(stepName));
  await mkdir(stepOutputDir, { recursive: true });
  return {
    stepOutputDir,
  };
}
