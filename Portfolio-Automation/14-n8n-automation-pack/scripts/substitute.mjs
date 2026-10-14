// Shared `${VAR_NAME}` -> environment variable substitution (A3: templates committed to the
// repo never contain real values). Used by render-credentials.mjs and render-workflows.mjs so
// both follow the exact same templating rule.

export function substituteEnvVars(text) {
  return text.replace(/\$\{([A-Z0-9_]+)\}/g, (match, name) => {
    const value = process.env[name];
    if (value === undefined) {
      throw new Error(`Missing environment variable referenced in template: ${name}`);
    }
    return value;
  });
}
