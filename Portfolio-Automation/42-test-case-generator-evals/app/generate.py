"""CLI entrypoint: python -m app.generate <requisito.json> --model <nombre>."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.generator import TestCaseGenerator
from app.llm import OpenAILLM, StubLLM
from app.models import Requirement


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate test cases for a requirement JSON file using a local or stub LLM."
    )
    parser.add_argument("requirement_file", type=str, help="Path to requirement JSON file")
    parser.add_argument(
        "--model",
        type=str,
        default="stub",
        help="Model name (e.g. 'stub' or Ollama model name like 'llama3.2')",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default=None,
        help="Optional base URL for OpenAI-compatible endpoint",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Optional timeout in seconds",
    )
    args = parser.parse_args()

    req_path = Path(args.requirement_file)
    if not req_path.is_file():
        sys.stderr.write(f"Error: Requirement file not found: {req_path}\n")
        sys.exit(1)

    try:
        with open(req_path, encoding="utf-8") as f:
            data = json.load(f)
        requirement = Requirement.model_validate(data)
    except Exception as e:
        sys.stderr.write(f"Error reading requirement {req_path}: {e}\n")
        sys.exit(1)

    if args.model.lower() == "stub":
        llm = StubLLM()
    else:
        llm = OpenAILLM(base_url=args.base_url, model=args.model, timeout=args.timeout)

    generator = TestCaseGenerator()
    result = generator.generate(requirement, llm)

    if result.error and not result.test_cases:
        sys.stderr.write(f"Generation failed after retry: {result.error}\n")
        sys.exit(1)

    output = {
        "requirement_id": result.requirement_id,
        "requirement_title": result.requirement_title,
        "valid_on_first_try": result.valid_on_first_try,
        "retries_used": result.retries_used,
        "test_cases": [tc.model_dump() for tc in result.test_cases],
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
