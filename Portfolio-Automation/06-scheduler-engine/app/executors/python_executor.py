import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.executors.base import ExecutionResult
from app.executors.shell_executor import resolve_job_path


def execute_python(payload: dict[str, Any], base_dir: Path | None = None) -> ExecutionResult:
    start = time.perf_counter()
    script_name = payload.get("script") or payload.get("file")
    if not script_name:
        return ExecutionResult(
            status="FAILED",
            stdout="",
            stderr="Missing required 'script' in PYTHON payload.",
            exit_code=-1,
            duration_ms=0,
        )

    args = payload.get("args") or []
    if not isinstance(args, list):
        args = [str(args)]
    else:
        args = [str(a) for a in args]

    timeout = float(payload.get("timeout") or settings.EXECUTION_TIMEOUT_SECONDS)

    try:
        script_path = resolve_job_path(script_name, base_dir=base_dir)
        if script_path.suffix != ".py":
            raise ValueError(f"Script '{script_name}' is not a Python (.py) file.")
    except (PermissionError, FileNotFoundError, ValueError) as err:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return ExecutionResult(
            status="FAILED",
            stdout="",
            stderr=str(err),
            exit_code=-1,
            duration_ms=duration_ms,
        )

    cmd_list = [sys.executable, str(script_path), *args]

    try:
        proc = subprocess.run(
            cmd_list,
            shell=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        duration_ms = int((time.perf_counter() - start) * 1000)
        stdout = (proc.stdout or "")[: settings.MAX_OUTPUT_BYTES]
        stderr = (proc.stderr or "")[: settings.MAX_OUTPUT_BYTES]
        status = "SUCCESS" if proc.returncode == 0 else "FAILED"

        return ExecutionResult(
            status=status,
            stdout=stdout,
            stderr=stderr,
            exit_code=proc.returncode,
            duration_ms=duration_ms,
        )
    except subprocess.TimeoutExpired:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return ExecutionResult(
            status="FAILED",
            stdout="",
            stderr=f"Python script timed out after {timeout} seconds.",
            exit_code=-1,
            duration_ms=duration_ms,
        )
    except Exception as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return ExecutionResult(
            status="FAILED",
            stdout="",
            stderr=f"Python execution error: {str(exc)}",
            exit_code=-1,
            duration_ms=duration_ms,
        )
