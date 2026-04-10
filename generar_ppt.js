import OpenAI from "openai";
import { spawn } from "node:child_process";
import { mkdirSync, existsSync } from "node:fs";
import { resolve } from "node:path";
import { loadEnvFile } from "node:process";

if (!process.env.OPENAI_API_KEY) {
  try {
    loadEnvFile(".env");
  } catch {
    // Ignore missing .env and fall back to the current environment.
  }
}

if (!process.env.OPENAI_API_KEY) {
  throw new Error(
    "OPENAI_API_KEY no esta definido. Configuralo en el entorno o en .env.",
  );
}

const MODEL = "gpt-5.4";
const CONTAINER_IMAGE = "python:3.12-slim";
const HOST_ROOT = resolve(".");
const HOST_OUTPUT_DIR = resolve("output");
const CONTAINER_ROOT = "/workspace";
const SKILL_PATH = resolve(".codex/skills/generar-presentacion");
const DEFAULT_REQUEST = [
  "Usa el skill generar-presentacion.",
  "Trabaja dentro de un contenedor Linux con Python 3.12.",
  "El repo esta montado en /workspace y la carpeta de salida escribible es /workspace/output.",
  "Crea una presentacion ejecutiva sobre las 5 tecnologias mas usadas en frontend en 2026.",
  "Guarda el archivo final en output/presentacion-top-frontend-2026.pptx.",
].join(" ");
const USER_REQUEST = process.argv.slice(2).join(" ").trim() || DEFAULT_REQUEST;

const client = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

const tools = [
  {
    type: "shell",
    environment: {
      type: "local",
      skills: [
        {
          name: "generar-presentacion",
          description:
            "Crea presentaciones desde una plantilla y contenido base.",
          path: SKILL_PATH,
        },
      ],
    },
  },
];

if (!existsSync(HOST_OUTPUT_DIR)) {
  mkdirSync(HOST_OUTPUT_DIR, { recursive: true });
}

function buildDockerArgs(command) {
  return [
    "run",
    "--rm",
    "--network",
    "none",
    "--cpus",
    "1",
    "--memory",
    "1g",
    "--read-only",
    "--tmpfs",
    "/tmp",
    "--mount",
    `type=bind,source=${HOST_ROOT},target=${CONTAINER_ROOT},readonly`,
    "--mount",
    `type=bind,source=${HOST_OUTPUT_DIR},target=${CONTAINER_ROOT}/output`,
    "--workdir",
    CONTAINER_ROOT,
    CONTAINER_IMAGE,
    "sh",
    "-lc",
    command,
  ];
}

function trimToBudget(text, remaining) {
  if (!text || remaining <= 0) {
    return { text: "", remaining: Math.max(remaining, 0) };
  }

  if (text.length <= remaining) {
    return { text, remaining: remaining - text.length };
  }

  return {
    text: `${text.slice(0, Math.max(remaining - 15, 0))}\n[truncated...]`,
    remaining: 0,
  };
}

function runCommand(command, timeoutMs) {
  return new Promise((resolveCommand, rejectCommand) => {
    const child = spawn("docker", buildDockerArgs(command), {
      cwd: process.cwd(),
      env: process.env,
      stdio: ["ignore", "pipe", "pipe"],
    });

    let stdout = "";
    let stderr = "";
    let timedOut = false;

    const timer = setTimeout(() => {
      timedOut = true;
      child.kill();
    }, timeoutMs);

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });

    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });

    child.on("error", (error) => {
      clearTimeout(timer);
      rejectCommand(error);
    });

    child.on("close", (code) => {
      clearTimeout(timer);
      resolveCommand({
        stdout,
        stderr,
        timedOut,
        exitCode: code ?? 1,
      });
    });
  });
}

async function ensureDockerReady() {
  const result = await runCommand("python --version", 30000).catch((error) => {
    throw new Error(
      `No se pudo invocar Docker desde este proceso: ${error.message}`,
    );
  });

  if (result.timedOut) {
    throw new Error("Docker no respondio a tiempo durante la validacion inicial.");
  }

  if (result.exitCode !== 0) {
    throw new Error(
      [
        "Docker no esta listo para ejecutar contenedores.",
        result.stderr || result.stdout || "Sin salida adicional.",
      ].join("\n"),
    );
  }
}

async function executeShellCall(shellCall) {
  const commands = shellCall.action?.commands ?? [];
  const timeoutMs = shellCall.action?.timeout_ms ?? 600000;
  const maxOutputLength = shellCall.action?.max_output_length ?? 12000;
  const output = [];
  let remaining = maxOutputLength;
  let status = "completed";

  for (const command of commands) {
    console.log(`\n$ ${command}`);

    const result = await runCommand(command, timeoutMs);
    const stdoutSlice = trimToBudget(result.stdout, remaining);
    remaining = stdoutSlice.remaining;
    const stderrSlice = trimToBudget(result.stderr, remaining);
    remaining = stderrSlice.remaining;

    if (stdoutSlice.text) {
      process.stdout.write(stdoutSlice.text);
    }

    if (stderrSlice.text) {
      process.stderr.write(stderrSlice.text);
    }

    output.push({
      stdout: stdoutSlice.text,
      stderr: stderrSlice.text,
      outcome: result.timedOut
        ? { type: "timeout" }
        : { type: "exit", exit_code: result.exitCode },
    });

    if (result.timedOut) {
      status = "incomplete";
      break;
    }
  }

  return {
    type: "shell_call_output",
    call_id: shellCall.call_id,
    max_output_length: maxOutputLength,
    status,
    output,
  };
}

async function runLocalShellFlow() {
  await ensureDockerReady();

  let response = await client.responses.create({
    model: MODEL,
    tools,
    input: USER_REQUEST,
  });

  while (true) {
    const shellCalls = (response.output ?? []).filter(
      (item) => item.type === "shell_call",
    );

    if (shellCalls.length === 0) {
      return response;
    }

    const shellOutputs = [];
    for (const shellCall of shellCalls) {
      shellOutputs.push(await executeShellCall(shellCall));
    }

    response = await client.responses.create({
      model: MODEL,
      tools,
      previous_response_id: response.id,
      input: shellOutputs,
    });
  }
}

const finalResponse = await runLocalShellFlow();

console.log("\nRespuesta final:\n");
console.log(finalResponse.output_text || JSON.stringify(finalResponse.output, null, 2));
