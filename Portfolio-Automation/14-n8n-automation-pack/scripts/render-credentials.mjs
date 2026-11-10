#!/usr/bin/env node
// Reads every credential template in `credentials/*.json` (A3: placeholders only, never real
// secrets), substitutes `${VAR_NAME}` with the matching environment variable, and writes a
// single combined array to the output path. Run inside n8n-init, never committed.

import { readFileSync, readdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { substituteEnvVars } from "./substitute.mjs";

const [, , inputDir, outputFile] = process.argv;
if (!inputDir || !outputFile) {
  console.error("Usage: render-credentials.mjs <credentials-dir> <output-file>");
  process.exit(1);
}

const files = readdirSync(inputDir).filter((name) => name.endsWith(".json")).sort();
const credentials = [];
for (const file of files) {
  const raw = readFileSync(join(inputDir, file), "utf8");
  const rendered = substituteEnvVars(raw);
  const parsed = JSON.parse(rendered);
  credentials.push(...parsed);
}

writeFileSync(outputFile, JSON.stringify(credentials, null, 2));
console.log(`Rendered ${credentials.length} credential(s) from ${files.length} template file(s).`);
