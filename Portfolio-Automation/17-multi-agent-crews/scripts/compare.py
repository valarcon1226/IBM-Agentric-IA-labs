"""Run both engines N times against the configured LLM and write docs/COMPARACION.md with measured numbers.

python scripts/compare.py              # uses LLM_BASE_URL / LLM_MODEL from .env (Ollama by default)
python scripts/compare.py --fake       # starts the fake LLM in-process (no model needed)
"""

import argparse
import os
import statistics
import sys
import threading
from datetime import date
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
TOPIC = "demanda de agentes de IA para atención al cliente en LATAM"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--fake", action="store_true")
    args = parser.parse_args()
    if args.fake:
        from fake_llm.server import Handler

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        os.environ.update(LLM_BASE_URL=f"http://127.0.0.1:{server.server_port}/v1", LLM_MODEL="fake")
    os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")

    from app import config
    from app.crews import autogen_team, crewai_crew

    rows = []
    for name, run, src in [
        ("CrewAI", crewai_crew.run, "crewai_crew.py"),
        ("AutoGen", autogen_team.run, "autogen_team.py"),
    ]:
        results = []
        for i in range(args.runs):
            r = run(TOPIC)
            print(
                f"{name} run {i + 1}: {r.seconds}s, {r.llm_calls} LLM calls, "
                f"{len(r.findings)} findings, sources={r.sources}"
            )
            results.append(r)
        loc = sum(1 for line in (ROOT / "app" / "crews" / src).read_text(encoding="utf-8").splitlines() if line.strip())
        rows.append(
            (
                name,
                statistics.mean(r.seconds for r in results),
                statistics.mean(r.llm_calls for r in results),
                sum(bool(r.findings and r.recommendations) for r in results),
                loc,
            )
        )

    model = "fake LLM (deterministic)" if args.fake else f"{config.LLM_MODEL} at {config.LLM_BASE_URL}"
    table = [
        "| Engine | Avg seconds | Avg LLM calls | Complete reports | Lines of code (non-blank) |",
        "|---|---|---|---|---|",
    ]
    table += [f"| {n} | {s:.1f} | {c:.1f} | {ok}/{args.runs} | {loc} |" for n, s, c, ok, loc in rows]
    print("\n".join(table))
    out = ROOT / "docs" / "COMPARACION.md"
    text = out.read_text(encoding="utf-8") if out.exists() else "# CrewAI vs AutoGen\n"
    head = text.split("<!-- measured -->")[0].rstrip()
    out.write_text(
        f"{head}\n\n<!-- measured -->\n## Medición ({date.today()}, {model}, {args.runs} corridas por motor)\n\n"
        + "\n".join(table)
        + "\n",
        encoding="utf-8",
    )
    print(f"written {out}")


if __name__ == "__main__":
    main()
