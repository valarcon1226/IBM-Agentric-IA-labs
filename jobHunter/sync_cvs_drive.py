"""Sube a Google Drive los CVs de las vacantes visibles y guarda un link público POR ARCHIVO (cualquiera con el link
puede ver ese CV, nada más) en jobs.cv_link, que el dashboard muestra para pegarlo en "link to your CV".
Corre en el HOST del homelab (no en Docker) con rclone y el remote "gdrive" (root_folder_id = carpeta de CVs).
Cron: */30 * * * * cd ~/homelab/jobhunter && python3 sync_cvs_drive.py >> sync_cvs_drive.log 2>&1"""
import datetime
import os
import sqlite3
import subprocess
import tempfile

RCLONE = os.path.expanduser("~/.local/bin/rclone")
REMOTE = "gdrive:"
CVS_DIR = "CVs_Listos"


def rclone(*args) -> str:
    return subprocess.run([RCLONE, *args], check=True, capture_output=True, text=True, timeout=600).stdout.strip()


def main():
    conn = sqlite3.connect("jobs.db")
    if "cv_link" not in {r[1] for r in conn.execute("PRAGMA table_info(jobs)")}:
        conn.execute("ALTER TABLE jobs ADD COLUMN cv_link TEXT")
    rows = conn.execute("SELECT id, cv_path FROM jobs WHERE cv_path IS NOT NULL AND cv_link IS NULL "
                        "AND status IN ('CV Generado', 'Aprobado', 'Match Insuficiente')").fetchall()
    # cv_path puede venir con ruta de Windows: se resuelve por nombre de archivo
    pending = [(jid, path.replace("\\", "/").rsplit("/", 1)[-1]) for jid, path in rows]
    pending = [(jid, name) for jid, name in pending if os.path.isfile(os.path.join(CVS_DIR, name))]
    print(f"{datetime.datetime.now():%Y-%m-%d %H:%M} | {len(pending)} CVs por subir")
    if not pending:
        return

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write("\n".join(name for _, name in pending))
    try:
        rclone("copy", CVS_DIR, REMOTE, "--files-from", f.name)  # no borra nada en Drive
    finally:
        os.unlink(f.name)

    for jid, name in pending:
        try:
            link = rclone("link", REMOTE + name)  # comparte SOLO este archivo: cualquiera con el link, lector
        except subprocess.CalledProcessError as e:
            print(f"  [-] {name}: {e.stderr.strip()[:200]}")
            continue
        conn.execute("UPDATE jobs SET cv_link = ? WHERE id = ?", (link, jid))
        conn.commit()
        print(f"  [+] {name} -> {link}")


if __name__ == "__main__":
    main()
