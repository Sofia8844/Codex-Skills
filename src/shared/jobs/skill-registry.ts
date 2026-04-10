import { resolve } from "node:path";
import { z } from "zod";

import type { AppEnvironment } from "../config/env.js";
import type { JobPayload } from "./job-types.js";

export interface SkillSpawnSpec {
  command: string;
  args: string[];
  cwd: string;
  env?: NodeJS.ProcessEnv;
  stdinText?: string;
  shell?: boolean;
  outputFile?: string | null;
}

export class UnknownSkillError extends Error {
  constructor(skillName: string) {
    super(`Skill "${skillName}" is not registered in the worker.`);
    this.name = "UnknownSkillError";
  }
}

const demoSkillPayloadSchema = z.object({
  message: z.string().optional().default("Demo skill executed successfully."),
  delayMs: z.coerce.number().int().positive().optional().default(1500),
  outputFile: z.string().optional(),
});
const generarPresentacionPayloadSchema = z.object({
  prompt: z.string().min(1),
  outputFile: z.string().optional().default("output/presentacion-final.pptx"),
  fullAuto: z.boolean().optional().default(false),
});
const codexExecPayloadSchema = z.object({
  prompt: z.string().min(1),
  workingDirectory: z.string().optional(),
  sandbox: z.string().optional().default("workspace-write"),
  fullAuto: z.boolean().optional().default(false),
  skipGitRepoCheck: z.boolean().optional().default(true),
  extraArgs: z.array(z.string()).optional().default([]),
  outputFile: z.string().optional(),
});

const codexPresentationPayloadSchema = z.object({
  prompt: z.string().optional(),
  fullAuto: z.boolean().optional().default(false),
  outputFile: z
    .string()
    .optional()
    .default("output/presentacion-top-frontend-2026-codex.pptx"),
});

type RegistryHandler = (payload: JobPayload, env: AppEnvironment) => SkillSpawnSpec;

function resolveWorkingDirectory(projectRoot: string, workingDirectory?: string) {
  if (!workingDirectory) {
    return projectRoot;
  }

  return resolve(projectRoot, workingDirectory);
}

const registry = new Map<string, RegistryHandler>([
  [
    "demo.echo",
    (payload, runtimeEnv) => {
      const parsed = demoSkillPayloadSchema.parse(payload);

      return {
        command: "node",
        args: [resolve(runtimeEnv.projectRoot, "skills/demo-skill.mjs"), JSON.stringify(parsed)],
        cwd: runtimeEnv.projectRoot,
        outputFile: parsed.outputFile ?? null,
      };
    },
  ],
  [
    "codex.exec",
    (payload, runtimeEnv) => {
      const parsed = codexExecPayloadSchema.parse(payload);
      const workingDirectory = resolveWorkingDirectory(
        runtimeEnv.projectRoot,
        parsed.workingDirectory,
      );
      const codexCommand = process.platform === "win32" ? "codex.cmd" : "codex";
      const args = [
        "exec",
        "-C",
        workingDirectory,
        "--sandbox",
        parsed.sandbox,
        ...(parsed.skipGitRepoCheck ? ["--skip-git-repo-check"] : []),
        ...parsed.extraArgs,
        "-",
      ];

      if (parsed.fullAuto) {
        args.push("--full-auto");
      }

      return {
        command: codexCommand,
        args,
        cwd: workingDirectory,
        stdinText: parsed.prompt,
        shell: process.platform === "win32",
        outputFile: parsed.outputFile ?? null,
      };
    },
  ],
  [
    "presentation.codex-script",
    (payload, runtimeEnv) => {
      const parsed = codexPresentationPayloadSchema.parse(payload);
      const args = [resolve(runtimeEnv.projectRoot, "generar_ppt_codex.js")];

      if (parsed.fullAuto) {
        args.push("--full-auto");
      }

      if (parsed.prompt) {
        args.push(parsed.prompt);
      }

      return {
        command: "node",
        args,
        cwd: runtimeEnv.projectRoot,
        outputFile: parsed.outputFile ?? null,
      };
    },
  ],
  [
  "generar-presentacion",
  (payload, runtimeEnv) => {
    const parsed = generarPresentacionPayloadSchema.parse(payload);
    const codexCommand = process.platform === "win32" ? "codex.cmd" : "codex";
    const skillPath = resolve(runtimeEnv.projectRoot, ".codex/skills/generar-presentacion");

    const args = [
      "exec",
      "-C",
      runtimeEnv.projectRoot,
/*       "--skip-git-repo-check",
      "--sandbox", 
      "workspace-write",*/
        "--skip-git-repo-check",
  "--dangerously-bypass-approvals-and-sandbox",
      "-",
    ];

    if (parsed.fullAuto) {
      args.push("--full-auto");
    }

    const prompt = [
      "Usa el skill generar-presentacion.",
      `El skill esta en ${skillPath}.`,
      parsed.prompt,
      `Guarda el archivo final en ${parsed.outputFile}.`,
    ].join(" ");

    return {
      command: codexCommand,
      args,
      cwd: runtimeEnv.projectRoot,
      stdinText: prompt,
      shell: process.platform === "win32",
      outputFile: parsed.outputFile,
    };
  },
],
  [
  "codex",
  (payload, runtimeEnv) => {
    const parsed = generarPresentacionPayloadSchema.parse(payload);
    const codexCommand = process.platform === "win32" ? "codex.cmd" : "codex";
    //const skillPath = resolve(runtimeEnv.projectRoot, ".codex/skills/generar-presentacion");

    const args = [
      "exec",
      "-C",
      runtimeEnv.projectRoot,
/*       "--skip-git-repo-check",
      "--sandbox", 
      "workspace-write",*/
        "--skip-git-repo-check",
  "--dangerously-bypass-approvals-and-sandbox",
      "-",
    ];

    if (parsed.fullAuto) {
      args.push("--full-auto");
    }

    const prompt = [
/*       "Usa el skill generar-presentacion.",
      `El skill esta en ${skillPath}.`, */
      parsed.prompt,
      `Guarda el archivo final en ${parsed.outputFile}.`,
    ].join(" ");

    return {
      command: codexCommand,
      args,
      cwd: runtimeEnv.projectRoot,
      stdinText: prompt,
      shell: process.platform === "win32",
      outputFile: parsed.outputFile,
    };
  },
],
]);

export function listAvailableSkills() {
  return [...registry.keys()];
}

export function isRegisteredSkill(skillName: string) {
  return registry.has(skillName);
}

export function resolveSkillExecution(
  skillName: string,
  payload: JobPayload,
  runtimeEnv: AppEnvironment,
) {
  const handler = registry.get(skillName);

  if (!handler) {
    throw new UnknownSkillError(skillName);
  }

  return handler(payload, runtimeEnv);
}
