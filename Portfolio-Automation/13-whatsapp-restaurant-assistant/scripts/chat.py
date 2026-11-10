"""Terminal chat client against POST /dev/chat (DECISIONES-13 W5), for building/demoing the
assistant without a real WhatsApp account.

Usage:
    python scripts/chat.py [wa_id]

Reads DEV_CHAT_URL (default http://localhost:8004/dev/chat) and DEV_API_KEY from the
environment.
"""

import json
import os
import sys
import urllib.error
import urllib.request

DEV_CHAT_URL = os.environ.get("DEV_CHAT_URL", "http://localhost:8004/dev/chat")
DEV_API_KEY = os.environ.get("DEV_API_KEY", "")


def send(wa_id: str, text: str) -> list[str]:
    body = json.dumps({"wa_id": wa_id, "text": text}).encode("utf-8")
    request = urllib.request.Request(
        DEV_CHAT_URL,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEV_API_KEY}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return list(json.loads(response.read())["replies"])
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')}") from exc


def main() -> None:
    wa_id = sys.argv[1] if len(sys.argv) > 1 else "573000000000"
    print(f"Chateando como {wa_id} contra {DEV_CHAT_URL}. Ctrl+C para salir.")
    while True:
        try:
            text = input("Tú: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not text:
            continue
        try:
            for reply in send(wa_id, text):
                print(f"Bot: {reply}")
        except RuntimeError as exc:
            print(f"Error: {exc}")


if __name__ == "__main__":
    main()
