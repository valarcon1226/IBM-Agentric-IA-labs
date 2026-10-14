"""Evaluation runner: executes evaluation suite, computes metrics, and generates reports."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from app.agent import RestaurantAgent
from app.db import init_db
from app.llm import BaseLLM, FakeLLM, OpenAILLM
from app.server import server as mcp_server
from evals.metrics import CaseEvaluationResult, evaluate_case

# cases.yaml uses concrete dates; pin 'today' so the suite does not rot as time passes.
os.environ.setdefault("RESERVAS_FECHA_REFERENCIA", "2026-10-14")


def load_eval_cases(cases_path: Path | None = None) -> list[dict[str, Any]]:
    """Load evaluation cases from YAML."""
    if cases_path is None:
        cases_path = Path(__file__).resolve().parent / "cases.yaml"
    with open(cases_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("cases", [])


async def run_eval_suite(
    model_name: str = "fake",
    cases_path: Path | None = None,
    reports_dir: Path | None = None,
) -> dict[str, Any]:
    """Execute all evaluation cases with the specified model and generate reports."""
    # Ensure database is initialized
    init_db()

    # Determine LLM instance
    llm: BaseLLM
    if model_name.lower() in ("fake", "deterministic"):
        llm = FakeLLM()
        display_model = "fake-deterministic"
    else:
        llm = OpenAILLM(model=model_name)
        display_model = model_name

    agent = RestaurantAgent(server=mcp_server, llm=llm)
    cases = load_eval_cases(cases_path)

    results: list[CaseEvaluationResult] = []
    for c in cases:
        resp = await agent.run(c["pregunta"])
        res = evaluate_case(c, resp)
        results.append(res)

    total_cases = len(results)
    passed_cases = sum(1 for r in results if r.passed_all)
    overall_accuracy = round(passed_cases / total_cases, 4) if total_cases else 0.0

    # Metric-specific counters
    tool_passed = sum(1 for r in results if r.herramienta_correcta)
    args_passed = sum(1 for r in results if r.argumentos_correctos)
    grounded_passed = sum(1 for r in results if r.respuesta_fundamentada)

    policy_cases = [r for r in results if r.rechazo_politica is not None]
    policy_passed = sum(1 for r in policy_cases if r.rechazo_politica)

    injection_cases = [r for r in results if r.defensa_injection is not None]
    injection_passed = sum(1 for r in injection_cases if r.defensa_injection)

    metrics_summary = {
        "herramienta_correcta": {
            "total": total_cases,
            "passed": tool_passed,
            "rate": round(tool_passed / total_cases, 4) if total_cases else 0.0,
            "percentage": f"{(tool_passed / total_cases) * 100:.1f}%" if total_cases else "0.0%",
        },
        "argumentos_correctos": {
            "total": total_cases,
            "passed": args_passed,
            "rate": round(args_passed / total_cases, 4) if total_cases else 0.0,
            "percentage": f"{(args_passed / total_cases) * 100:.1f}%" if total_cases else "0.0%",
        },
        "respuesta_fundamentada": {
            "total": total_cases,
            "passed": grounded_passed,
            "rate": round(grounded_passed / total_cases, 4) if total_cases else 0.0,
            "percentage": f"{(grounded_passed / total_cases) * 100:.1f}%"
            if total_cases
            else "0.0%",
        },
        "rechazo_pedidos_fuera_politica": {
            "total": len(policy_cases),
            "passed": policy_passed,
            "rate": round(policy_passed / len(policy_cases), 4) if policy_cases else 1.0,
            "percentage": f"{(policy_passed / len(policy_cases)) * 100:.1f}%"
            if policy_cases
            else "100.0%",
        },
        "defensa_prompt_injection": {
            "total": len(injection_cases),
            "passed": injection_passed,
            "rate": round(injection_passed / len(injection_cases), 4) if injection_cases else 1.0,
            "percentage": f"{(injection_passed / len(injection_cases)) * 100:.1f}%"
            if injection_cases
            else "100.0%",
        },
    }

    report_payload = {
        "model": display_model,
        "timestamp": datetime.now(UTC).isoformat(),
        "total_cases": total_cases,
        "passed_cases": passed_cases,
        "overall_accuracy": overall_accuracy,
        "overall_percentage": f"{overall_accuracy * 100:.1f}%",
        "metrics": metrics_summary,
        "detailed_results": [
            {
                "case_id": r.case_id,
                "categoria": r.categoria,
                "pregunta": r.pregunta,
                "herramienta_esperada": r.herramienta_esperada,
                "herramienta_obtenida": r.herramienta_obtenida,
                "passed_all": r.passed_all,
                "herramienta_correcta": r.herramienta_correcta,
                "argumentos_correctos": r.argumentos_correctos,
                "respuesta_fundamentada": r.respuesta_fundamentada,
                "rechazo_politica": r.rechazo_politica,
                "defensa_injection": r.defensa_injection,
                "notes": r.notes,
            }
            for r in results
        ],
    }

    # Generate Markdown and JSON reports
    if reports_dir is None:
        reports_dir = Path(__file__).resolve().parent.parent / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    json_path = reports_dir / "eval.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report_payload, f, indent=2, ensure_ascii=False)

    md_path = reports_dir / "eval.md"
    markdown_content = generate_markdown_report(report_payload, results)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)

    return report_payload


def generate_markdown_report(data: dict[str, Any], results: list[CaseEvaluationResult]) -> str:
    """Format evaluation outcome into a clean GitHub-Flavored Markdown report."""
    md: list[str] = []
    md.append("# Reporte de Evaluación de Agente MCP — Sabor de Casa\n")
    md.append(f"- **Modelo Evaluado:** `{data['model']}`")
    md.append(f"- **Fecha y Hora (UTC):** `{data['timestamp']}`")
    md.append(f"- **Casos Totales:** {data['total_cases']}")
    md.append(f"- **Casos Aprobados:** {data['passed_cases']} / {data['total_cases']}")
    md.append(f"- **Tasa Global de Acierto:** **{data['overall_percentage']}**\n")

    md.append("## Resumen de Rendimiento por Métrica\n")
    md.append("| Métrica | Total Casos | Aprobados | Tasa de Acierto | Estado |")
    md.append("| :--- | :---: | :---: | :---: | :---: |")

    for metric_name, mdata in data["metrics"].items():
        status = (
            "✅ PASS"
            if mdata["rate"] == 1.0
            else ("⚠️ PARCIAL" if mdata["rate"] >= 0.7 else "❌ FAIL")
        )
        clean_name = metric_name.replace("_", " ").capitalize()
        tot = mdata["total"]
        pas = mdata["passed"]
        pct = mdata["percentage"]
        md.append(f"| **{clean_name}** | {tot} | {pas} | {pct} | {status} |")

    md.append("\n## Detalle de Casos de Evaluación\n")
    md.append("| ID | Categoría | Herramienta Esperada | Herramienta Obtenida | Estado | Notas |")
    md.append("| :--- | :--- | :--- | :--- | :---: | :--- |")

    for r in results:
        status = "✅ PASS" if r.passed_all else "❌ FAIL"
        tool_exp = r.herramienta_esperada or "(ninguna)"
        tool_act = r.herramienta_obtenida or "(ninguna)"
        notes_str = r.notes or "OK"
        md.append(
            f"| `{r.case_id}` | `{r.categoria}` | `{tool_exp}` | `{tool_act}` | {status} | "
            f"{notes_str} |"
        )

    md.append("\n## Conclusiones y Análisis de Calidad\n")
    if data["overall_accuracy"] == 1.0:
        md.append(
            "- **Conformidad Total (100%):** El agente demostró selección exacta de "
            "herramientas, extracción precisa de parámetros, respuestas completamente "
            "fundamentadas en las políticas y menú, rechazo riguroso de solicitudes "
            "fuera de política y neutralización efectiva de prompt injection."
        )
    else:
        md.append(
            f"- **Acierto Parcial ({data['overall_percentage']}):** Revisar casos con fallas "
            "en la tabla superior para ajustar el prompting o refinamiento de herramientas."
        )

    return "\n".join(md) + "\n"


def main() -> None:
    """CLI runner entrypoint."""
    parser = argparse.ArgumentParser(
        description="Suite de Evaluación para Agente MCP Sabor de Casa"
    )
    parser.add_argument(
        "--model",
        default="fake",
        help="Modelo a evaluar ('fake' para determinista local, o nombre de modelo Ollama/OpenAI)",
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=None,
        help="Ruta al archivo cases.yaml",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=None,
        help="Directorio de destino para reportes",
    )
    args = parser.parse_args()

    print(f"[INFO] Iniciando evaluacion con modelo: {args.model}...")
    res = asyncio.run(
        run_eval_suite(model_name=args.model, cases_path=args.cases, reports_dir=args.reports_dir)
    )
    print(
        f"[OK] Evaluacion finalizada: {res['passed_cases']}/{res['total_cases']} casos "
        f"aprobados ({res['overall_percentage']})."
    )
    print("Reportes generados en reports/eval.md y reports/eval.json.")


if __name__ == "__main__":
    main()
