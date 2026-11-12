from dataclasses import dataclass


@dataclass
class ExecutionResult:
    status: str  # "SUCCESS" or "FAILED"
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int
