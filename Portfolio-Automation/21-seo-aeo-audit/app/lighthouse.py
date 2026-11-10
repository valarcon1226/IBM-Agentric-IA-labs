"""Lighthouse headless execution and score extraction."""

import json
import os
import shutil
import subprocess
import tempfile
from typing import Any


def find_browser_executable() -> str | None:
    """Find Google Chrome or Microsoft Edge executable on the system."""
    env_path = os.environ.get("CHROME_PATH")
    if env_path and os.path.exists(env_path):
        return env_path

    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path

    which_chrome = shutil.which("msedge") or shutil.which("google-chrome") or shutil.which("chrome")
    return which_chrome


def run_lighthouse_audit(
    url: str,
    timeout_seconds: int = 60,
    skip_if_missing: bool = True,
) -> dict[str, Any]:
    """
    Execute `npx lighthouse` headless against the given URL and extract the 4 category scores.
    If Chrome/Edge is missing or command fails, return a graceful fallback result.
    """
    npx_bin = shutil.which("npx") or shutil.which("npx.cmd")
    browser_bin = find_browser_executable()

    if not browser_bin or not npx_bin:
        reason = "Edge/Chrome no detectado en el entorno." if not browser_bin else "Node.js / npx no disponible."
        return {
            "available": False,
            "skipped": True,
            "reason": f"Lighthouse omitido: {reason} El informe se genera con auditoría estática.",
            "performance": None,
            "accessibility": None,
            "best_practices": None,
            "seo": None,
        }

    with tempfile.TemporaryDirectory() as tmp_dir:
        output_json = os.path.join(tmp_dir, "lighthouse_report.json")
        env = os.environ.copy()
        env["CHROME_PATH"] = browser_bin

        cmd = [
            npx_bin,
            "lighthouse",
            url,
            "--output=json",
            f"--output-path={output_json}",
            '--chrome-flags=--headless --no-sandbox --disable-gpu',
            "--only-categories=performance,accessibility,best-practices,seo",
            "--quiet",
        ]

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                env=env,
                shell=(os.name == "nt"),
            )

            if res.returncode != 0 and not os.path.exists(output_json):
                return {
                    "available": False,
                    "skipped": True,
                    "reason": f"Lighthouse falló con código {res.returncode}: {res.stderr.strip()[:200]}",
                    "performance": None,
                    "accessibility": None,
                    "best_practices": None,
                    "seo": None,
                }

            if not os.path.exists(output_json):
                return {
                    "available": False,
                    "skipped": True,
                    "reason": "Lighthouse no generó el archivo de resultados.",
                    "performance": None,
                    "accessibility": None,
                    "best_practices": None,
                    "seo": None,
                }

            with open(output_json, encoding="utf-8") as f:
                data = json.load(f)

            categories = data.get("categories", {})
            perf = categories.get("performance", {}).get("score")
            a11y = categories.get("accessibility", {}).get("score")
            bp = categories.get("best-practices", {}).get("score")
            seo = categories.get("seo", {}).get("score")

            def to_score(val: float | None) -> int | None:
                return round(val * 100) if val is not None else None

            return {
                "available": True,
                "skipped": False,
                "reason": "Auditoría Lighthouse completada exitosamente.",
                "performance": to_score(perf),
                "accessibility": to_score(a11y),
                "best_practices": to_score(bp),
                "seo": to_score(seo),
            }

        except subprocess.TimeoutExpired:
            return {
                "available": False,
                "skipped": True,
                "reason": f"Lighthouse excedió el tiempo límite ({timeout_seconds}s).",
                "performance": None,
                "accessibility": None,
                "best_practices": None,
                "seo": None,
            }
        except Exception as ex:
            return {
                "available": False,
                "skipped": True,
                "reason": f"Error ejecutando Lighthouse: {ex}",
                "performance": None,
                "accessibility": None,
                "best_practices": None,
                "seo": None,
            }
