"""Download your own Coursera course content (videos, transcripts, readings) for personal study.

Usage:
    py coursera.py login                          # plain Edge window, log in once (session kept in edge_profile/)
    py coursera.py cursos                         # list your enrolled courses (slugs)
    py coursera.py <course-url-or-slug> [--modulo N]
    py coursera.py https://www.coursera.org/specializations/<slug>   # every course, in order

Output: courses/<slug>/<NN module>/<NN lesson>/<NN item>.{mp4,en.vtt,en.txt,md} + course.json
Labs and quizzes are saved as a .md stub with their link (labs run in IBM's JupyterLab, not downloadable here).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup
from markdownify import markdownify
from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
PROFILE = HERE / "edge_profile"
# \\?\ lifts Windows' 260-char path limit: project dir + module/lesson/item names easily exceed it
OUT = Path("\\\\?\\" + str((HERE / "courses").resolve())) if os.name == "nt" else HERE / "courses"
BASE = "https://www.coursera.org"
EDGE_PATHS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]
RESOLUTIONS = ["720p", "540p", "360p", "1080p"]  # 720p first: good enough to study, ~half the size of 1080p
SUBTITLE_LANGS = ["en", "es"]
MATERIALS = (
    "/api/onDemandCourseMaterials.v2/?q=slug&slug={slug}&includes=modules,lessons,items"
    "&fields=moduleIds,onDemandCourseMaterialModules.v1(name,slug,lessonIds),"
    "onDemandCourseMaterialLessons.v1(name,slug,itemIds),"
    "onDemandCourseMaterialItems.v2(name,slug,contentSummary,lessonId,moduleId)"
)


def open_session(p):
    """Persistent Edge context: cookies survive between runs, so login happens once."""
    return p.chromium.launch_persistent_context(str(PROFILE), channel="msedge", headless=True)


def manual_login():
    """Plain Edge (no automation flags) so Google sign-in doesn't flag it as 'not secure'.
    Same profile dir, so the automated session reuses its cookies afterwards."""
    edge = next((e for e in EDGE_PATHS if Path(e).exists()), None)
    if not edge:
        sys.exit("No encontré msedge.exe.")
    print("Inicia sesión en Coursera en la ventana de Edge y CIERRA esa ventana al terminar...")
    subprocess.run([edge, f"--user-data-dir={PROFILE}", "--no-first-run", f"{BASE}/?authMode=login"])


def has_session(ctx):
    return any(c["name"] == "CAUTH" for c in ctx.cookies(BASE))


def api(ctx, path):
    r = ctx.request.get(BASE + path)
    if not r.ok:
        raise RuntimeError(f"HTTP {r.status} en {path.split('?')[0]}")
    return r.json()


def safe(name):
    """Windows-safe file name."""
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "", name).strip()[:60].strip().rstrip(".") or "sin-nombre"


def fetch(url, dest):
    """Stream a signed CDN file to disk; .part + rename so an interrupted run never leaves a half file."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    with urllib.request.urlopen(url, timeout=60) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f)
    tmp.replace(dest)


def cml_to_md(cml, resolve_asset=None):
    """Coursera's CML (text/heading/list/code/img/asset) -> Markdown.
    resolve_asset(asset_id) -> local relative path; None leaves images/files out."""
    soup = BeautifulSoup(cml, "html.parser")  # html.parser lowercases attrs: assetId -> assetid
    for t in soup.find_all("text"):
        t.name = "p"
    for h in soup.find_all("heading"):
        h.name = f"h{h.get('level', '2')}"
    for lst in soup.find_all("list"):
        lst.name = "ol" if lst.get("bullettype") == "numbers" else "ul"
    for c in soup.find_all("code"):
        c.name = "pre"
    for img in soup.find_all("img"):
        if resolve_asset and img.get("assetid"):
            img["src"] = resolve_asset(img["assetid"])
        else:
            img.decompose()
    for a in soup.find_all("asset"):
        if resolve_asset and a.get("id"):
            path = resolve_asset(a["id"])
            a.replace_with(soup.new_tag("a", href=path, string=Path(path).name))
        else:
            a.decompose()
    md = markdownify(str(soup), heading_style="ATX")
    md = re.sub(r"(!\[[^\]]*\]\([^)]*\))", r"\n\n\1\n\n", md)  # images on their own line
    return re.sub(r"\n{3,}", "\n\n", md).strip() + "\n"


def save_lecture(ctx, cid, it, base):
    video = api(ctx, f"/api/onDemandLectureVideos.v1/{cid}~{it['id']}?includes=video"
                     "&fields=onDemandVideos.v1(sources,subtitlesVtt,subtitlesTxt)")["linked"]["onDemandVideos.v1"][0]
    for lang in SUBTITLE_LANGS:
        for kind, ext in (("subtitlesVtt", "vtt"), ("subtitlesTxt", "txt")):
            url = video.get(kind, {}).get(lang)
            dest = base.with_name(f"{base.name}.{lang}.{ext}")
            if url and not dest.exists():
                r = ctx.request.get(BASE + url if url.startswith("/") else url)
                if r.ok:
                    dest.write_bytes(r.body())
    dest = base.with_name(base.name + ".mp4")
    if not dest.exists():
        by_res = video["sources"].get("byResolution", {})
        url = next((by_res[r]["mp4VideoUrl"] for r in RESOLUTIONS if r in by_res), None)
        if not url:
            raise RuntimeError("sin mp4 disponible")
        fetch(url, dest)


def save_supplement(ctx, cid, it, base):
    dest = base.with_name(base.name + ".md")
    if dest.exists():
        return
    assets = api(ctx, f"/api/onDemandSupplements.v1/{cid}~{it['id']}?includes=asset"
                      "&fields=openCourseAssets.v1(typeName),openCourseAssets.v1(definition)")["linked"]["openCourseAssets.v1"]

    def resolve(asset_id):
        a = api(ctx, f"/api/assets.v1?ids={asset_id}&fields=fileName,url")["elements"][0]
        # id prefix: readings in one lesson often reuse names like "1.PNG"
        local = dest.parent / "assets" / f"{asset_id[:8]}-{safe(a['name'])}"
        if not local.exists():
            fetch(a["url"]["url"], local)
        return f"assets/{local.name}"

    body = "\n".join(cml_to_md(a["definition"].get("value", ""), resolve) for a in assets if a["typeName"] == "cml")
    dest.write_text(f"# {it['name']}\n\n{body}", encoding="utf-8")


def save_stub(slug, it, base):
    dest = base.with_name(base.name + ".md")
    if not dest.exists():
        kind = it["contentSummary"]["typeName"]
        dest.write_text(f"# {it['name']}\n\nTipo: `{kind}` (no descargable, ábrelo en Coursera)\n\n"
                        f"{BASE}/learn/{slug}/item/{it['id']}\n", encoding="utf-8")


def download(ctx, slug, only_module=None):
    d = api(ctx, MATERIALS.format(slug=slug))
    course, linked = d["elements"][0], d["linked"]
    modules = {m["id"]: m for m in linked["onDemandCourseMaterialModules.v1"]}
    lessons = {x["id"]: x for x in linked["onDemandCourseMaterialLessons.v1"]}
    items = {x["id"]: x for x in linked["onDemandCourseMaterialItems.v2"]}
    if any(mid not in modules for mid in course["moduleIds"]):
        raise RuntimeError(f"Coursera no devuelve el contenido de '{slug}': inscríbete en el curso y vuelve a ejecutar")
    root = OUT / slug
    root.mkdir(parents=True, exist_ok=True)
    (root / "course.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")

    done, failed = 0, []
    for mi, mid in enumerate(course["moduleIds"], 1):
        if only_module and mi != only_module:
            continue
        m = modules[mid]
        print(f"\n== Módulo {mi}: {m['name']}")
        for li, lid in enumerate(m["lessonIds"], 1):
            les = lessons[lid]
            folder = root / f"{mi:02d} {safe(m['name'])}" / f"{li:02d} {safe(les['name'])}"
            folder.mkdir(parents=True, exist_ok=True)
            for ii, iid in enumerate(les["itemIds"], 1):
                it = items.get(iid)
                if not it:  # Coursera hides some items (usually graded) when you're not enrolled
                    failed.append(f"elemento {iid} oculto por Coursera (¿no inscrita?)")
                    print(f"  [x] elemento {iid} oculto por Coursera")
                    continue
                kind = it["contentSummary"]["typeName"]
                base = folder / f"{ii:02d} {safe(it['name'])}"
                print(f"  [{kind}] {it['name']}")
                try:
                    if kind == "lecture":
                        save_lecture(ctx, course["id"], it, base)
                    elif kind == "supplement":
                        save_supplement(ctx, course["id"], it, base)
                    else:
                        save_stub(slug, it, base)
                    done += 1
                except Exception as e:  # one broken item must not stop the course; reported at the end
                    failed.append(f"{it['name']}: {e}")
                    print(f"    [x] {e}")
    print(f"\nListo: {done} elementos en {root}")
    if failed:
        print(f"{len(failed)} fallaron (vuelve a ejecutar para reintentar, lo ya bajado se salta):")
        print("\n".join(f"  - {f}" for f in failed))
    return not failed


def main():
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("curso", help="login | cursos | URL o slug del curso")
    ap.add_argument("--modulo", type=int, help="solo este módulo (1, 2, ...)")
    args = ap.parse_args()
    if args.curso == "login":
        manual_login()
    with sync_playwright() as p:
        ctx = open_session(p)
        try:
            if not has_session(ctx):
                sys.exit("No hay sesión de Coursera (cookie CAUTH). Ejecuta: py coursera.py login")
            if args.curso == "login":
                print("Sesión OK.")
            elif args.curso == "cursos":
                d = api(ctx, "/api/memberships.v1?q=me&showHidden=true&includes=courseId&fields=courses.v1(name,slug)")
                for c in d["linked"].get("courses.v1", []):
                    print(f"{c['slug']:<70} {c['name'].strip()}")
            elif spec := re.search(r"/specializations/([^/?#]+)", args.curso):
                d = api(ctx, f"/api/onDemandSpecializations.v1?q=slug&slug={spec.group(1)}"
                             "&fields=courseIds,courses.v1(slug,name)&includes=courseIds")
                slugs = {c["id"]: c["slug"] for c in d["linked"]["courses.v1"]}
                failed = []
                for n, cid in enumerate(d["elements"][0]["courseIds"], 1):  # courseIds keeps the official order
                    print(f"\n######## Curso {n}: {slugs[cid]}")
                    try:
                        if not download(ctx, slugs[cid], args.modulo):
                            failed.append(slugs[cid])
                    except Exception as e:  # e.g. not enrolled: keep going with the other courses
                        print(f"[x] {e}")
                        failed.append(slugs[cid])
                if failed:
                    print("\nCursos con fallos:", ", ".join(failed))
                sys.exit(1 if failed else 0)
            else:
                m = re.search(r"/learn/([^/?#]+)", args.curso)
                ok = download(ctx, m.group(1) if m else args.curso.strip("/"), args.modulo)
                sys.exit(0 if ok else 1)
        finally:
            ctx.close()


if __name__ == "__main__":
    main()
