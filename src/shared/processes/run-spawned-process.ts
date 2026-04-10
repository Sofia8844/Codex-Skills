import { spawn } from "node:child_process";

import { createLogger } from "../logging/logger.js";
import type { SkillSpawnSpec } from "../jobs/skill-registry.js";

const logger = createLogger("shared:spawn");

class OutputCollector {
  private current = "";

  constructor(private readonly maxChars: number) {}

  append(chunk: string) {
    if (this.current.length >= this.maxChars) {
      return;
    }

    const remaining = this.maxChars - this.current.length;
    this.current += chunk.slice(0, remaining);

    if (chunk.length > remaining) {
      this.current += "\n[truncated]";
    }
  }

  toString() {
    return this.current;
  }
}

export interface SpawnResult {
  exitCode: number | null;
  signal: NodeJS.Signals | null;
  stdout: string;
  stderr: string;
}

export async function runSpawnedProcess(
  spec: SkillSpawnSpec,
  maxOutputChars: number,
) {
  logger.info("Starting child process", {
    command: spec.command,
    args: spec.args,
    cwd: spec.cwd,
  });

  return await new Promise<SpawnResult>((resolveResult, rejectResult) => {
    const stdoutCollector = new OutputCollector(maxOutputChars);
    const stderrCollector = new OutputCollector(maxOutputChars);

    const child = spawn(spec.command, spec.args, {
      cwd: spec.cwd,
      env: {
        ...process.env,
        ...spec.env,
      },
      shell: spec.shell ?? false,
      stdio: ["pipe", "pipe", "pipe"],
      windowsHide: true,
    });

    child.stdout.on("data", (chunk: Buffer) => {
      stdoutCollector.append(chunk.toString());
    });

    child.stderr.on("data", (chunk: Buffer) => {
      stderrCollector.append(chunk.toString());
    });

    child.on("error", (error) => {
      rejectResult(error);
    });

    child.on("close", (code, signal) => {
      logger.info("Child process finished", {
        command: spec.command,
        exitCode: code,
        signal,
      });

      resolveResult({
        exitCode: code,
        signal,
        stdout: stdoutCollector.toString(),
        stderr: stderrCollector.toString(),
      });
    });

    if (spec.stdinText) {
      child.stdin.write(spec.stdinText);
    }

    child.stdin.end();
  });
}
