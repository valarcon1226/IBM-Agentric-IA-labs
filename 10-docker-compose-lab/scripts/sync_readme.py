"""Keep README sections 6-8 identical to the files they document.

Usage (from 10-docker-compose-lab):
    py -3 scripts/sync_readme.py          # rewrite README.md
    py -3 scripts/sync_readme.py --check  # exit 1 if README.md is out of date
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (start marker, end marker, new heading, intro, code language, source file)
SECTIONS = [
    (
        "## 6. Environment Variables",
        "## 7. docker-compose.yml",
        "## 6. Environment Variables (.env.example)",
        "Verbatim copy of `.env.example`. The postgres superuser password is **not** read from\n"
        "`.env`: it comes from the Docker secret `secrets/db_password.txt` "
        "(`POSTGRES_PASSWORD_FILE`).",
        "env",
        ".env.example",
    ),
    (
        "## 7. docker-compose.yml",
        "## 8. Database Initialization",
        "## 7. docker-compose.yml (Complete)",
        "Verbatim copy of `docker-compose.yml` (regenerate with `py -3 scripts/sync_readme.py`).",
        "yaml",
        "docker-compose.yml",
    ),
    (
        "## 8. Database Initialization",
        "## 9. Implementation Steps",
        "## 8. Database Initialization (init-db.sh)",
        "Verbatim copy of `init-db.sh`. Role passwords come from the environment.",
        "bash",
        "init-db.sh",
    ),
]


def render(readme: str) -> str:
    for start, end, heading, intro, lang, source in SECTIONS:
        a, b = readme.index(start), readme.index(end)
        body = (ROOT / source).read_text(encoding="utf-8").rstrip("\n")
        readme = readme[:a] + f"{heading}\n{intro}\n\n```{lang}\n{body}\n```\n\n" + readme[b:]
    return readme


def main() -> int:
    path = ROOT / "README.md"
    current = path.read_text(encoding="utf-8")
    expected = render(current)
    if "--check" in sys.argv:
        if current != expected:
            print("README.md is out of date: run py -3 scripts/sync_readme.py")
            return 1
        print("README.md in sync")
        return 0
    path.write_text(expected, encoding="utf-8", newline="\n")
    print("README.md updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
