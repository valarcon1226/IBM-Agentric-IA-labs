"""Compare each course's course.json (what Coursera lists) with the files on disk, item by item.

Usage: py verify_coursera.py <Certificaciones root> [slug ...]
Finds every <root>/<topic>/<slug>/course.json. Exit 1 if anything is missing.
"""
import json
import sys
from pathlib import Path

from coursera import long_path, safe


def check(root):
    d = json.loads((root / "course.json").read_text(encoding="utf-8"))
    course, linked = d["elements"][0], d["linked"]
    modules = {m["id"]: m for m in linked["onDemandCourseMaterialModules.v1"]}
    lessons = {x["id"]: x for x in linked["onDemandCourseMaterialLessons.v1"]}
    items = {x["id"]: x for x in linked["onDemandCourseMaterialItems.v2"]}
    total, missing, hidden = 0, [], 0
    for mi, mid in enumerate(course["moduleIds"], 1):
        m = modules[mid]
        for li, lid in enumerate(m["lessonIds"], 1):
            folder = root / f"{mi:02d} {safe(m['name'])}" / f"{li:02d} {safe(lessons[lid]['name'])}"
            for ii, iid in enumerate(lessons[lid]["itemIds"], 1):
                it = items.get(iid)
                if not it:
                    hidden += 1
                    continue
                total += 1
                stem = f"{ii:02d} {safe(it['name'])}"
                kind = it["contentSummary"]["typeName"]
                need = [".mp4"] if kind == "lecture" else [".md"]
                for ext in need:
                    f = folder / (stem + ext)
                    if not f.exists() or f.stat().st_size == 0:
                        missing.append(f"{kind}: {mi}.{li}.{ii} {it['name']} (falta {ext})")
                if kind == "lecture" and not any(folder.glob(f"{stem}*.vtt".replace("[", "[[]"))):
                    missing.append(f"lecture: {mi}.{li}.{ii} {it['name']} (sin subtítulos)")
    return total, hidden, missing


if __name__ == "__main__":
    base = long_path(sys.argv[1])
    only = set(sys.argv[2:])
    bad = 0
    for cj in sorted(base.glob("*/*/course.json")):
        if only and cj.parent.name not in only:
            continue
        total, hidden, missing = check(cj.parent)
        print(f"{'OK ' if not missing else 'FALTA'} {cj.parent.parent.name}/{cj.parent.name}: "
              f"{total - len(missing)}/{total} items, {hidden} ocultos por Coursera")
        for m in missing:
            print("    -", m)
        bad += bool(missing)
    sys.exit(1 if bad else 0)
