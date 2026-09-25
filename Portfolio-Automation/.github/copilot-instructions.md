# Copilot instructions — Portfolio-Automation

These rules apply to **every** chat/agent session in this workspace. Read them before acting.
Work is organised as numbered task files in `docs/tasks/`. Your job is to execute **one task
file at a time, exactly as written**. You are an executor, not a designer.

## How to execute a task

1. Open `docs/tasks/README.md`, find the task the user named (e.g. `T03`). Check the
   prerequisites in the task's own **"Antes de empezar"** section (e.g. "`T02` en `DONE`"). If one
   is not met, stop and tell the user which one is missing.
2. Read the whole task file before editing anything.
3. Run the task's **"Antes de empezar"** commands and confirm the output matches what the task
   says. If it does not match, **stop and report** — the repo is not in the state the task expects.
4. Do the steps **in order**. When a step gives code in a block marked `EXACTO`, copy it
   exactly. Do not rename, restructure, "improve", add features, add comments, or reformat it.
5. After the last step run the task's **"Verificación"** commands. Every expected result must
   match. The number of passing tests must be **exactly** the number stated.
6. Write the report (format below) in the chat, then mark the task `DONE` in
   `docs/tasks/README.md` (only that one line).

## Hard rules

- **Never mark anything done without running its verification command and pasting the real output.**
- **Scope:** touch only the files the task lists. If you believe another file must change,
  stop and ask.
- **When exact code fails** (a test, ruff or mypy error): you may make the *smallest* change
  that fixes it (typing, an import, a typo). You may **not** change behaviour, delete or weaken
  a test, add `# type: ignore`, `# noqa`, `pytest.skip`, or `xfail`. Explain every deviation in
  the report under "Desviaciones".
- If after 2 attempts a verification still fails, **stop** and report the full error. Do not
  keep trying variations.
- **HTTP contract = the Pydantic models in `app/api/routes/*.py`.** Never document or test
  request bodies from Celery task arguments.
- README and EXECUTION_PLAN change together; after changing a concept, search for every
  mention with `Select-String` and fix them all.
- Write files with the editor tools (UTF-8, no BOM, LF line endings). Never use
  `Set-Content` / `Out-File` / `>` to write source files.
- **Never write or edit file content through PowerShell strings.** PowerShell expands `$VAR`
  and `${VAR}` inside double-quoted strings and here-strings, silently turning
  `${FASTAPI_DB_PASSWORD}` into an empty string (this broke `docker-compose.yml` in T11).
  Use the editor tools only. After editing any file that contains `$`, re-read it and confirm
  every `${...}` is still there.
- **Never edit text just to make a verification pass.** If a check matches text that legitimately
  describes the problem (docs, risk tables, history), report it as a false positive in
  "Dudas o contradicciones". Do not reword, rename or change the search pattern.
- Do not commit, push, create branches, delete files, or install global tools unless the task
  says so. Never read, print or edit anything under `10-docker-compose-lab/secrets/`.
- Do not edit `docs/tasks/*.md` except to mark a task `DONE`.
- **If a task contradicts what you see in the code or docs, stop and report the contradiction.**
  Never invent a third version.
- No invented numbers: coverage, test counts, versions and dates come from command output.
- Terminal is **PowerShell 5.1**: no `&&`; use `;` or separate commands.
- **Ponytail rule — simplest thing that works.** If your tool has the `ponytail` skill, load it
  before writing code. Either way, apply its ladder to all code you write that is not marked
  `EXACTO`: question whether it needs to exist (YAGNI), reuse what is already in the repo,
  standard library before custom code, native features before new dependencies, one line
  before fifty. Never cut validation, error handling, security or tests to make code shorter.
  `EXACTO` code is still copied as-is: if you see a simpler version, propose it in the report
  under "Dudas o contradicciones" instead of changing it.

## Quality gates — project 04 (run from `04-data-cleaning-api`)

```powershell
if (-not (Test-Path .venv)) { uv venv -p 3.12 .venv; uv pip install -p .venv\Scripts\python.exe -r requirements-dev.txt }
.venv\Scripts\ruff.exe check app tests
.venv\Scripts\ruff.exe format --check app tests
.venv\Scripts\mypy.exe app
.venv\Scripts\python.exe -m pytest --timeout=60 --cov -p no:cacheprovider
```

Expected: `All checks passed!` · `N files already formatted` · `Success: no issues found` ·
`<exact number from the task> passed`, 0 failed, 0 errors. If `ruff format --check` fails, run
`.venv\Scripts\ruff.exe format app tests` once and re-run all gates. If `requirements-dev.txt`
changed in the task, re-run the `uv pip install` line first.

## Report format (paste in chat at the end of every task)

```
## Tarea TXX — <título>
Estado: DONE | BLOQUEADA (<motivo>)
Archivos modificados: <lista>
Desviaciones del código EXACTO: <ninguna | lista con motivo>
Verificación:
<comando>
<salida real, recortada a lo relevante>
Tests: <N passed> (esperado: <N>) · Cobertura: <X%>
Dudas o contradicciones encontradas: <ninguna | lista>
```
