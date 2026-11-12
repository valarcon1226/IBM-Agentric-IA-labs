"""Target assertion against targets.toml definitions."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any


def load_targets(targets_path: str | Path | None = None) -> dict[str, Any]:
    """Find and load targets.toml from path or parent directories."""
    if targets_path is not None:
        p = Path(targets_path)
        if not p.is_file():
            raise FileNotFoundError(f"targets.toml not found at {p}")
        with p.open("rb") as f:
            return tomllib.load(f)

    # Search in current directory and parents
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        candidate = parent / "targets.toml"
        if candidate.is_file():
            with candidate.open("rb") as f:
                return tomllib.load(f)

    raise FileNotFoundError("targets.toml not found in current directory or any parent")


def assert_target(
    name: str,
    value: float,
    targets_path: str | Path | None = None,
) -> None:
    """Assert that measured value meets the limit specified in targets.toml.

    Fails with a message naming the target, the limit, and the measured value.
    """
    data = load_targets(targets_path)

    # Allow flat key or key under [targets] section
    targets_dict = data.get("targets", data)
    if name not in targets_dict:
        raise KeyError(f"Target '{name}' not found in targets.toml")

    limit = targets_dict[name]

    # For rate/recovery/percent targets: must be >= limit
    # For latency/count/diff/error targets: must be <= limit
    is_lower_bounded = name.endswith(("_percent", "_ratio", "_rate"))

    if is_lower_bounded:
        if value < limit:
            raise AssertionError(
                f"Target '{name}' failed: minimum required is {limit}, "
                f"but measured value was {value}"
            )
    else:
        if value > limit:
            raise AssertionError(
                f"Target '{name}' failed: maximum limit is {limit}, "
                f"but measured value was {value}"
            )
