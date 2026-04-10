import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";

const rawPayload = process.argv[2];

if (!rawPayload) {
  console.error("Missing payload argument.");
  process.exit(1);
}

const payload = JSON.parse(rawPayload);
const delayMs = Number(payload.delayMs ?? 1500);
const message = String(payload.message ?? "Demo skill executed successfully.");
const outputFile = payload.outputFile ? resolve(String(payload.outputFile)) : null;

console.log(`[demo-skill] Starting job with delay ${delayMs}ms`);

await new Promise((resolveDelay) => {
  setTimeout(resolveDelay, delayMs);
});

console.log(`[demo-skill] ${message}`);

if (outputFile) {
  mkdirSync(dirname(outputFile), { recursive: true });
  writeFileSync(
    outputFile,
    `${new Date().toISOString()} :: ${message}\n`,
    "utf8",
  );
  console.log(`[demo-skill] Output file written to ${outputFile}`);
}

process.exit(0);
