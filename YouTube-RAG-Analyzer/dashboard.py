"""Local dashboard: paste YouTube links, get every report as a card. Run: py dashboard.py"""
import json
import queue
import re
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from main import CACHE_DIR, RESULTS_DIR, sanitize_filename
from tools import _VIDEO_ID_PATTERN

ROOT = Path(__file__).parent
RESULTS = ROOT / RESULTS_DIR
QUEUE_FILE = ROOT / "cola.json"  # pending URLs, so a crash or Ctrl+C doesn't lose the queue
PORT = 8765
MAX_LINES = 50

jobs = []  # [{"url", "status", "log"}], shown in the page; lives only while the server runs
work = queue.Queue()
save_lock = threading.Lock()


def save_queue():
    """Write every URL not finished yet; write-then-rename so a crash mid-save keeps the old file."""
    with save_lock:
        pending = [j["url"] for j in jobs if j["status"] in ("en cola", "procesando")]
        tmp = QUEUE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(pending, indent=1), encoding="utf-8")
        tmp.replace(QUEUE_FILE)


def enqueue(urls):
    for url in urls:
        job = {"url": url, "status": "en cola", "log": ""}
        jobs.append(job)
        work.put(job)
    save_queue()


def resume_queue():
    """Re-queue what was pending last time, minus videos that got their report before the stop."""
    try:
        urls = json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    done = {v["id"] for v in load_videos()}
    todo = [u for u in urls if not ((m := _VIDEO_ID_PATTERN.search(u)) and m.group(1) in done)]
    enqueue(todo)
    if todo:
        print(f"Retomando {len(todo)} link(s) pendientes de {QUEUE_FILE.name}")


def ids_by_title() -> dict:
    """Older reports have no video_id in their front matter; recover it from the metadata cache."""
    ids = {}
    for f in (ROOT / CACHE_DIR).glob("*.json"):
        try:
            title = json.loads(f.read_text(encoding="utf-8"))["metadata"].get("title") or ""
        except (OSError, ValueError, KeyError):
            continue
        ids[sanitize_filename(title)] = f.stem
    return ids


def load_videos() -> list:
    ids = ids_by_title()
    videos = []
    for md in RESULTS.rglob("*.md"):
        text = md.read_text(encoding="utf-8", errors="replace")
        m = re.match(r"---\n(.*?)\n---\n", text, re.S)
        front = dict(re.findall(r"^(\w+): (.+)$", m.group(1), re.M)) if m else {}
        body = text[m.end():] if m else text
        title = re.search(r"^# (.+)$", body, re.M)
        source = re.search(r"Channel: (.*?) \| Duration: ([\d:]+)", body)
        videos.append({
            "id": front.get("video_id") or ids.get(md.stem, ""),
            "title": title.group(1).strip() if title else md.stem,
            "channel": source.group(1) if source else "",
            "duration": source.group(2) if source else "",
            # The folder wins: main.py files reports by category, and you may move them by hand
            "category": md.parent.name if md.parent != RESULTS else front.get("category", "Sin clasificar"),
            "added": md.stat().st_mtime,
            "report": body,
        })
    return videos


def worker():
    # ponytail: one video at a time, the free LLM quota is the bottleneck anyway
    while True:
        job = work.get()
        job["status"] = "procesando"
        try:
            r = subprocess.run([sys.executable, str(ROOT / "main.py"), job["url"]], cwd=ROOT,
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
            out = r.stdout + r.stderr
        except OSError as e:
            out = f"[ERROR] {e}"
        # main.py prints [ERROR] and exits 0 on bad input, so judge by its success line
        job["status"] = "listo" if "Documento de conocimiento" in out else "error"
        job["log"] = out[-1500:]
        save_queue()


class Handler(BaseHTTPRequestHandler):
    def send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/":
            self.send(200, (ROOT / "dashboard.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/videos":
            self.send(200, load_videos())
        elif self.path == "/api/jobs":
            self.send(200, jobs)
        else:
            self.send(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/api/analyze":
            return self.send(404, {"error": "not found"})
        try:
            length = int(self.headers.get("Content-Length", 0))
            text = json.loads(self.rfile.read(min(length, 100_000)))["urls"]
            lines = [l.strip() for l in str(text).splitlines() if l.strip()]
        except (ValueError, KeyError, TypeError):
            return self.send(400, {"error": "Body debe ser {\"urls\": \"...\"}"})
        if not lines or len(lines) > MAX_LINES or any(len(l) > 300 for l in lines):
            return self.send(400, {"error": f"Entre 1 y {MAX_LINES} links, uno por linea"})
        enqueue(lines)
        self.send(200, {"queued": len(lines)})

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    resume_queue()
    threading.Thread(target=worker, daemon=True).start()
    url = f"http://127.0.0.1:{PORT}"
    print(f"Dashboard en {url}  (Ctrl+C para salir)")
    if sys.platform == "win32":
        subprocess.Popen(["cmd", "/c", "start", "msedge", url])
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
