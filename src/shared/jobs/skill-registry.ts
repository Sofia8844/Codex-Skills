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
const networkDesignPayloadSchema = z.object({
  inputFile: z.string().min(1),
  outputDir: z.string().min(1),
  caseRootDir: z.string().min(1).optional(),
  caseDescription: z.string().min(1).optional(),
  explanationFile: z.string().min(1).optional(),
});
const networkQuotePayloadSchema = z.object({
  inputFile: z.string().min(1),
  outputDir: z.string().min(1),
  caseRootDir: z.string().min(1).optional(),
  explanationFile: z.string().min(1).optional(),
});
const proposalPayloadSchema = z.object({
  designHandoffPath: z.string().min(1),
  quoteOutputPath: z.string().min(1),
  outputDir: z.string().min(1),
  caseRootDir: z.string().min(1).optional(),
  userInputFile: z.string().min(1).optional(),
  templatePath: z.string().min(1).optional(),
  finalPresentationPath: z.string().min(1).optional(),
  build: z.boolean().optional().default(true),
});

type RegistryHandler = (payload: JobPayload, env: AppEnvironment) => SkillSpawnSpec;

function resolveWorkingDirectory(projectRoot: string, workingDirectory?: string) {
  if (!workingDirectory) {
    return projectRoot;
  }

  return resolve(projectRoot, workingDirectory);
}

function getCodexCommand() {
  return process.platform === "win32" ? "codex.cmd" : "codex";
}

function buildCodexExecArgs(
  workingDirectory: string,
  options?: {
    fullAuto?: boolean;
    extraArgs?: string[];
    bypassSandbox?: boolean;
  },
) {
  const fullAuto = options?.fullAuto ?? true;
  const extraArgs = options?.extraArgs ?? [];
  const bypassSandbox = options?.bypassSandbox ?? false;

  return [
    "exec",
    "-C",
    workingDirectory,
    "--skip-git-repo-check",
    ...(bypassSandbox
      ? ["--dangerously-bypass-approvals-and-sandbox"]
      : ["--sandbox", "workspace-write"]),
    ...extraArgs,
    ...(fullAuto && !bypassSandbox ? ["--full-auto"] : []),
    "-",
  ];
}

function buildCodexSkillPrompt({
  skillName,
  skillPath,
  caseRootDir,
  outputDir,
  inputPaths,
  expectedArtifacts,
  extraInstructions = [],
}: {
  skillName: string;
  skillPath: string;
  caseRootDir?: string;
  outputDir: string;
  inputPaths: string[];
  expectedArtifacts: string[];
  extraInstructions?: string[];
}) {
  const lines = [
    `Usa el skill ${skillName}.`,
    `El skill esta en ${skillPath}.`,
    "Ejecuta el trabajo de forma completamente no interactiva dentro de esta sesion de Codex CLI.",
    `La carpeta de salida del step es ${outputDir}.`,
    ...(caseRootDir
      ? [
          `Este job pertenece al caso ${caseRootDir}.`,
          `No escribas archivos fuera de ${caseRootDir}. Solo puedes leer fuera de esa carpeta si es para consumir assets internos del skill o archivos fuente del repositorio.`,
        ]
      : []),
    ...(inputPaths.length > 0
      ? [
          "Entradas obligatorias:",
          ...inputPaths.map((path, index) => `${index + 1}. ${path}`),
        ]
      : []),
    "Artefactos esperados:",
    ...expectedArtifacts.map((artifact, index) => `${index + 1}. ${artifact}`),
    ...extraInstructions,
    "Si necesitas archivos intermedios, dejalos dentro de la carpeta de salida del step.",
    "No uses rutas manuales arbitrarias ni analysis_output global fuera del caso actual.",
    "Al finalizar, verifica que los artefactos esperados existan en las rutas indicadas.",
  ];

  return lines.join("\n");
}

function buildCodexSkillSpec(
  runtimeEnv: AppEnvironment,
  prompt: string,
  outputFile?: string | null,
  workingDirectory = runtimeEnv.projectRoot,
) {
  return {
    command: getCodexCommand(),
    args: buildCodexExecArgs(workingDirectory, {
      fullAuto: false,
      bypassSandbox: true,
    }),
    cwd: workingDirectory,
    stdinText: prompt,
    shell: process.platform === "win32",
    outputFile: outputFile ?? null,
  };
}

function buildNetworkDesignPrompt(payload: z.infer<typeof networkDesignPayloadSchema>, runtimeEnv: AppEnvironment) {
  const skillPath = resolve(runtimeEnv.projectRoot, ".codex/skills/diseno-redes-empresariales");
  const expectedArtifacts = [
    resolve(payload.outputDir, "network_design_handoff.json"),
    resolve(payload.outputDir, "network_design_explanation.md"),
    resolve(payload.outputDir, "network_design_explanation.pdf"),
  ];

  return buildCodexSkillPrompt({
    skillName: "diseno-redes-empresariales",
    skillPath,
    outputDir: payload.outputDir,
    ...(payload.caseRootDir ? { caseRootDir: payload.caseRootDir } : {}),
    inputPaths: payload.caseDescription ? [] : [payload.inputFile],
    expectedArtifacts,
    extraInstructions: [
      ...(payload.caseDescription
        ? [
            "Analiza el caso principalmente desde el requerimiento en lenguaje natural incluido a continuacion.",
            "",
            "Caso a analizar:",
            payload.caseDescription,
          ]
        : [`Lee el requerimiento estructurado desde ${payload.inputFile}.`]),
      "Genera la explicacion visible en Markdown y luego deja el handoff JSON y el PDF en la misma carpeta de salida.",
      ...(payload.explanationFile
        ? [`Si ya existe una explicacion visible definitiva, reutilizala desde ${payload.explanationFile}.`]
        : []),
    ],
  });
}

function buildNetworkQuotePrompt(payload: z.infer<typeof networkQuotePayloadSchema>, runtimeEnv: AppEnvironment) {
  const skillPath = resolve(runtimeEnv.projectRoot, ".codex/skills/cotizacion-redes-empresariales");
  const expectedArtifacts = [
    resolve(payload.outputDir, "network_quote_output.json"),
    resolve(payload.outputDir, "network_quote_explanation.md"),
    resolve(payload.outputDir, "network_quote_explanation.pdf"),
  ];

  return buildCodexSkillPrompt({
    skillName: "cotizacion-redes-empresariales",
    skillPath,
    outputDir: payload.outputDir,
    ...(payload.caseRootDir ? { caseRootDir: payload.caseRootDir } : {}),
    inputPaths: [payload.inputFile],
    expectedArtifacts,
    extraInstructions: [
      `Consume el handoff o input comercial desde ${payload.inputFile}.`,
      "No recalcules diseno; solo transforma el input recibido a cotizacion preliminar, explicacion visible y PDF dentro de la carpeta del step.",
      ...(payload.explanationFile
        ? [`Si ya existe una explicacion visible definitiva, reutilizala desde ${payload.explanationFile}.`]
        : []),
    ],
  });
}

function buildProposalPrompt(payload: z.infer<typeof proposalPayloadSchema>, runtimeEnv: AppEnvironment) {
  const skillPath = resolve(runtimeEnv.projectRoot, ".codex/skills/creacion-propuesta");
  const finalPresentationPath =
    payload.finalPresentationPath ?? resolve(payload.outputDir, "propuesta-economica-final.pptx");
  const expectedArtifacts = [
    resolve(payload.outputDir, "proposal_network_context.json"),
    resolve(payload.outputDir, "proposal_network_spec.json"),
    ...(payload.build ? [finalPresentationPath] : []),
  ];

  return buildCodexSkillPrompt({
    skillName: "creacion-propuesta",
    skillPath,
    outputDir: payload.outputDir,
    ...(payload.caseRootDir ? { caseRootDir: payload.caseRootDir } : {}),
    inputPaths: [payload.designHandoffPath, payload.quoteOutputPath],
    expectedArtifacts,
    extraInstructions: [
      `Lee el handoff de diseno desde ${payload.designHandoffPath}.`,
      `Lee la salida de cotizacion desde ${payload.quoteOutputPath}.`,
      ...(payload.userInputFile ? [`Si existe input adicional del usuario, incorporalo desde ${payload.userInputFile}.`] : []),
      ...(payload.templatePath ? [`Usa esta plantilla si aplica: ${payload.templatePath}.`] : []),
      ...(payload.build
        ? [`Construye la presentacion final y guardala exactamente en ${finalPresentationPath}. Si el spec generado apunta a otra ruta, ajustalo para que el PPTX final quede dentro de ${payload.outputDir}.`]
        : ["No construyas el PPTX final; deja listo el contexto y el spec JSON para una construccion posterior."]),
      "No recalcules diseno ni cotizacion. Solo integra, estructura y genera los artefactos de propuesta.",
    ],
  });
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
        ...(parsed.fullAuto ? ["--full-auto"] : []),
        "-",
      ];

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
    "diseno-redes-empresariales",
    (payload, runtimeEnv) => {
      const parsed = networkDesignPayloadSchema.parse(payload);
      return buildCodexSkillSpec(
        runtimeEnv,
        buildNetworkDesignPrompt(parsed, runtimeEnv),
        resolve(parsed.outputDir, "network_design_handoff.json"),
      );
    },
  ],
  [
    "cotizacion-redes-empresariales",
    (payload, runtimeEnv) => {
      const parsed = networkQuotePayloadSchema.parse(payload);
      return buildCodexSkillSpec(
        runtimeEnv,
        buildNetworkQuotePrompt(parsed, runtimeEnv),
        resolve(parsed.outputDir, "network_quote_output.json"),
      );
    },
  ],
  [
    "creacion-propuesta",
    (payload, runtimeEnv) => {
      const parsed = proposalPayloadSchema.parse(payload);
      const finalPresentationPath =
        parsed.finalPresentationPath ?? resolve(parsed.outputDir, "propuesta-economica-final.pptx");

      return buildCodexSkillSpec(
        runtimeEnv,
        buildProposalPrompt(parsed, runtimeEnv),
        parsed.build
          ? finalPresentationPath
          : resolve(parsed.outputDir, "proposal_network_spec.json"),
      );
    },
  ],
  [
    "generar-presentacion",
  (payload, runtimeEnv) => {
    const parsed = generarPresentacionPayloadSchema.parse(payload);
    const skillPath = resolve(runtimeEnv.projectRoot, ".codex/skills/generar-presentacion");
    const args = buildCodexExecArgs(runtimeEnv.projectRoot, {
      fullAuto: parsed.fullAuto,
      bypassSandbox: false,
    });

    const prompt = [
      "Usa el skill generar-presentacion.",
      `El skill esta en ${skillPath}.`,
      parsed.prompt,
      `Guarda el archivo final en ${parsed.outputFile}.`,
    ].join(" ");

    return {
      command: getCodexCommand(),
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
    const args = buildCodexExecArgs(runtimeEnv.projectRoot, {
      fullAuto: parsed.fullAuto,
      bypassSandbox: false,
    });

    const prompt = [
/*       "Usa el skill generar-presentacion.",
      `El skill esta en ${skillPath}.`, */
      parsed.prompt,
      `Guarda el archivo final en ${parsed.outputFile}.`,
    ].join(" ");

    return {
      command: getCodexCommand(),
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
