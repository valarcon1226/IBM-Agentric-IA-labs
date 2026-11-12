#!/usr/bin/env node
// Reads every workflow in `workflows/*.json`, substitutes `${VAR_NAME}` placeholders (same
// templating approach as render-credentials.mjs, A3), and writes each rendered file to the
// output directory for `n8n import:workflow`. This keeps the committed workflow JSON free of
// real values (e.g. the LLM endpoint) instead of having n8n read them from `$env` at runtime
// (follow-up fix: `N8N_BLOCK_ENV_ACCESS_IN_NODE` back to its secure default).

import { mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { substituteEnvVars } from "./substitute.mjs";

const [, , inputDir, outputDir] = process.argv;
if (!inputDir || !outputDir) {
  console.error("Usage: render-workflows.mjs <workflows-dir> <output-dir>");
  process.exit(1);
}

mkdirSync(outputDir, { recursive: true });
const files = readdirSync(inputDir).filter((name) => name.endsWith(".json")).sort();
for (const file of files) {
  const raw = readFileSync(join(inputDir, file), "utf8");
  writeFileSync(join(outputDir, file), substituteEnvVars(raw));
}

console.log(`Rendered ${files.length} workflow file(s) from ${inputDir} to ${outputDir}.`);
