#!/usr/bin/env node
// Prints the id of every workflow in `workflows/*.json` whose exported JSON has `"active": true`,
// one per line. n8n-init.sh uses this to know which workflows to activate after import, instead
// of hardcoding ids (DECISIONES-14 A2: "los importa ... y los activa").

import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

const [, , inputDir] = process.argv;
if (!inputDir) {
  console.error("Usage: list-active-workflow-ids.mjs <workflows-dir>");
  process.exit(1);
}

const files = readdirSync(inputDir).filter((name) => name.endsWith(".json")).sort();
for (const file of files) {
  const workflow = JSON.parse(readFileSync(join(inputDir, file), "utf8"));
  if (workflow.active === true && workflow.id) {
    console.log(workflow.id);
  }
}
