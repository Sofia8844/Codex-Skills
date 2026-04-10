import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import process from "node:process";

const repoDir = resolve(".");
const skillPath = resolve(".codex/skills/generar-presentacion");

if (!existsSync(skillPath)) {
  throw new Error(
    `No encontre el skill generar-presentacion en: ${skillPath}`,
  );
}

const rawArgs = process.argv.slice(2);
const useFullAuto = rawArgs.includes("--full-auto");
const promptArgs = rawArgs.filter((arg) => arg !== "--full-auto");

const defaultPrompt = [
  "Usa el skill generar-presentacion.",
  `El skill esta en ${skillPath}.`,
  "Crea una presentacion ejecutiva sobre las 5 tecnologias mas usadas en frontend en 2026.",
  "Guarda el archivo final en output/presentacion-top-frontend-2026-codex.pptx.",
].join(" ");

const prompt = promptArgs.join(" ").trim() || defaultPrompt;

const codexArgs = [
  "exec",
  "-C",
  repoDir,
  "--skip-git-repo-check",
  "--sandbox",
  "workspace-write",
  "-",
];

if (useFullAuto) {
  codexArgs.push("--full-auto");
}

const codexCommand = process.platform === "win32" ? "codex.cmd" : "codex";
const useShell = process.platform === "win32";

console.log("Ejecutando Codex con estos argumentos:");
console.log([codexCommand, ...codexArgs].join(" "));

const child = spawn(codexCommand, codexArgs, {
  cwd: repoDir,
  env: process.env,
  stdio: ["pipe", "inherit", "inherit"],
  shell: useShell,
});

child.stdin.write(prompt);
child.stdin.end();

child.on("error", (error) => {
  console.error("No se pudo ejecutar codex:", error.message);
  process.exit(1);
});

child.on("close", (code) => {
  process.exit(code ?? 1);
});
