import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.executors.base import ExecutionResult


def resolve_job_path(file_name: str, base_dir: Path | None = None) -> Path:
    jobs_dir = (base_dir or settings.jobs_path).resolve()
    # Strip leading slashes to prevent absolute path override
    clean_name = file_name.lstrip("/\\")
    resolved = (jobs_dir / clean_name).resolve()

    if not resolved.is_relative_to(jobs_dir):
        msg = f"Access denied: '{file_name}' resolves outside the allowed jobs directory."
        raise PermissionError(msg)

    if not resolved.exists() or not resolved.is_file():
        msg = f"Job script '{file_name}' not found in allowed jobs directory ({jobs_dir})."
        raise FileNotFoundError(msg)

    return resolved


def execute_shell(payload: dict[str, Any], base_dir: Path | None = None) -> ExecutionResult:
    start = time.perf_counter()
    command_str = payload.get("command") or payload.get("script")
    if not command_str:
        return ExecutionResult(
            status="FAILED",
            stdout="",
            stderr="Missing required 'command' or 'script' in SHELL payload.",
            exit_code=-1,
            duration_ms=0,
        )

    # Arguments can be passed as a list or extracted
    args = payload.get("args") or []
    if not isinstance(args, list):
        args = [str(args)]
    else:
        args = [str(a) for a in args]

    timeout = float(payload.get("timeout") or settings.EXECUTION_TIMEOUT_SECONDS)

    try:
        script_path = resolve_job_path(command_str, base_dir=base_dir)
    except (PermissionError, FileNotFoundError) as err:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return ExecutionResult(
            status="FAILED",
            stdout="",
            stderr=str(err),
            exit_code=-1,
            duration_ms=duration_ms,
        )

    # Determine execution invocation without shell=True
    cmd_list: list[str]
    if script_path.suffix == ".py":
        cmd_list = [sys.executable, str(script_path), *args]
    elif script_path.suffix == ".sh":
        if os.path.exists("/bin/sh"):
            cmd_list = ["/bin/sh", str(script_path), *args]
        elif shutil.which("bash"):
            cmd_list = [shutil.which("bash"), str(script_path), *args]  # type: ignore[list-item]
        elif shutil.which("sh"):
            cmd_list = [shutil.which("sh"), str(script_path), *args]  # type: ignore[list-item]
        else:
            cmd_list = [str(script_path), *args]
    else:
        cmd_list = [str(script_path), *args]

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
            stderr=f"Command timed out after {timeout} seconds.",
            exit_code=-1,
            duration_ms=duration_ms,
        )
    except Exception as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return ExecutionResult(
            status="FAILED",
            stdout="",
            stderr=f"Subprocess execution error: {str(exc)}",
            exit_code=-1,
            duration_ms=duration_ms,
        )
