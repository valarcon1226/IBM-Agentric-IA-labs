# Gemini — read this first

The rules for any AI agent working in this folder are in
[`.github/copilot-instructions.md`](.github/copilot-instructions.md). They apply to you exactly
as written, even though the file is named for Copilot. Read that file completely before you act.

In short:
- Work comes from numbered task files in [`docs/tasks/`](docs/tasks/README.md). Execute **one
  task per session**, in order, and only the task the user names.
- Copy code marked `EXACTO` without changing it. Touch only the files the task lists.
- Nothing counts as done without running its verification command and pasting the real output.
- If a task contradicts the code or docs, stop and report. Do not invent a third version.
- No commits, pushes or deletions unless the task says so. Never read `10-docker-compose-lab/secrets/`.

Known defects and why each task exists:
- Project 04: [`04-data-cleaning-api/docs/RISK-ANALYSIS.md`](04-data-cleaning-api/docs/RISK-ANALYSIS.md)
- Project 10: [`10-docker-compose-lab/docs/RISK-ANALYSIS.md`](10-docker-compose-lab/docs/RISK-ANALYSIS.md)
