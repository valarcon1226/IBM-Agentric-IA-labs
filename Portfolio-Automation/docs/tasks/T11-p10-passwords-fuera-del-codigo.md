# T11 — P10: sacar las contraseñas de los archivos versionados

**Problema actual:** `10-docker-compose-lab/init-db.sql` y `docker-compose.yml` tienen en texto
plano las contraseñas de `fastapi_user`, `n8n_user` y `grafana_user` (`*_secure_pass`).
**Objetivo:**
- las contraseñas salen de variables de entorno (`.env`, no versionado);
- `init-db.sql` se reemplaza por `init-db.sh`, que las lee;
- el README se regenera con un script en lugar de copiarse a mano.

**Archivos que puedes tocar (todos dentro de `10-docker-compose-lab/`, salvo el primero):**
- `Portfolio-Automation/.gitattributes` (nuevo, en la raíz de `Portfolio-Automation`)
- `init-db.sh` (nuevo) · `init-db.sql` (se **borra**, autorizado por esta tarea)
- `docker-compose.yml` · `.env.example`
- `scripts/sync_readme.py` (nuevo) · `README.md` · `TROUBLESHOOTING.md` · `EXECUTION_PLAN.md`
- `docs/RISK-ANALYSIS.md` (solo la columna Status de DL-R04)

## Antes de empezar

- **No depende de T01–T10**: puede ejecutarse en cualquier momento, antes o después de ellas.
- Desde `10-docker-compose-lab`:
  `Select-String -Path docker-compose.yml, init-db.sql -Pattern "_secure_pass"` → **7** coincidencias
  (4 en docker-compose.yml, 3 en init-db.sql). Si no son 7, detente.

## Paso 1 — `Portfolio-Automation/.gitattributes` (nuevo)

EXACTO (garantiza que los `.sh` tengan fin de línea LF aunque se editen en Windows; con CRLF
el script falla dentro del contenedor Linux):

```
*.sh text eol=lf
```

## Paso 2 — `init-db.sh` (nuevo)

EXACTO. Después de guardarlo, en la barra de estado de VS Code confirma que dice **LF** (no
CRLF); si dice CRLF, haz clic y cámbialo a LF y guarda de nuevo.

```bash
#!/bin/bash
# Runs once, on the first start of the postgres container (docker-entrypoint-initdb.d).
# Creates one database + owner role per service. Passwords come from the environment
# (see .env.example); nothing secret is stored in this file.
set -eo pipefail

: "${FASTAPI_DB_PASSWORD:?FASTAPI_DB_PASSWORD is required}"
: "${N8N_DB_PASSWORD:?N8N_DB_PASSWORD is required}"
: "${GRAFANA_DB_PASSWORD:?GRAFANA_DB_PASSWORD is required}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
  -v fastapi_pw="$FASTAPI_DB_PASSWORD" \
  -v n8n_pw="$N8N_DB_PASSWORD" \
  -v grafana_pw="$GRAFANA_DB_PASSWORD" <<'EOSQL'
CREATE USER fastapi_user WITH PASSWORD :'fastapi_pw';
CREATE DATABASE fastapi_db OWNER fastapi_user;
GRANT ALL PRIVILEGES ON DATABASE fastapi_db TO fastapi_user;

CREATE USER n8n_user WITH PASSWORD :'n8n_pw';
CREATE DATABASE n8n_db OWNER n8n_user;
GRANT ALL PRIVILEGES ON DATABASE n8n_db TO n8n_user;

CREATE USER grafana_user WITH PASSWORD :'grafana_pw';
CREATE DATABASE grafana_db OWNER grafana_user;
GRANT ALL PRIVILEGES ON DATABASE grafana_db TO grafana_user;

\c fastapi_db
GRANT ALL ON SCHEMA public TO fastapi_user;

\c n8n_db
GRANT ALL ON SCHEMA public TO n8n_user;

\c grafana_db
GRANT ALL ON SCHEMA public TO grafana_user;
EOSQL
```

## Paso 3 — borrar `init-db.sql`

`Remove-Item init-db.sql` (autorizado solo en esta tarea).

## Paso 4 — `docker-compose.yml` (6 cambios, uno por línea; no toques nada más)

| # | Busca exactamente | Reemplaza por |
| - | ----------------- | ------------- |
| 1 | `      - ./init-db.sql:/docker-entrypoint-initdb.d/init-db.sql:ro` | `      - ./init-db.sh:/docker-entrypoint-initdb.d/init-db.sh:ro` |
| 2 | `      POSTGRES_PASSWORD_FILE: /run/secrets/db_password` | las 4 líneas del bloque de abajo |
| 3 | `      - DATABASE_URL=postgresql://fastapi_user:fastapi_secure_pass@postgres:5432/fastapi_db` (aparece **2** veces: `fastapi-gateway` y `celery-worker`; cambia ambas) | `      - DATABASE_URL=postgresql://fastapi_user:${FASTAPI_DB_PASSWORD}@postgres:5432/fastapi_db` |
| 4 | `      - DB_POSTGRESDB_PASSWORD=n8n_secure_pass` | `      - DB_POSTGRESDB_PASSWORD=${N8N_DB_PASSWORD}` |
| 5 | `      - GF_DATABASE_PASSWORD=grafana_secure_pass` | `      - GF_DATABASE_PASSWORD=${GRAFANA_DB_PASSWORD}` |

Bloque para el cambio 2. EXACTO (6 espacios de sangría, igual que la línea original):

```yaml
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
      FASTAPI_DB_PASSWORD: ${FASTAPI_DB_PASSWORD}
      N8N_DB_PASSWORD: ${N8N_DB_PASSWORD}
      GRAFANA_DB_PASSWORD: ${GRAFANA_DB_PASSWORD}
```

## Paso 5 — `.env.example`

Justo **después** de la línea `DB_PASSWORD=change_me_to_a_secure_password` agrega. EXACTO:

```
# Per-service database roles (created by init-db.sh). Letters and digits only:
# they are embedded in connection URLs.
FASTAPI_DB_PASSWORD=change_me_fastapi
N8N_DB_PASSWORD=change_me_n8n
GRAFANA_DB_PASSWORD=change_me_grafana
```

## Paso 6 — `scripts/sync_readme.py` (nuevo)

EXACTO:

```python
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
```

Luego ejecuta: `py -3 scripts/sync_readme.py` → `README.md updated`.

## Paso 7 — resto del `README.md` (a mano, solo estas líneas)

- Sección 4 (árbol): `├── init-db.sql` → `├── init-db.sh`, y agrega debajo de
  `├── prometheus.yml` la línea `├── scripts/sync_readme.py`.
- Sección 5 (tabla): `(runs `init-db.sql`)` → `(runs `init-db.sh`)`.
- Sección 9, paso 3: `Write one `init-db.sql` that creates schemas per service.` →
  `Write one `init-db.sh` that creates one database and role per service, reading passwords from the environment.`

## Paso 8 — `TROUBLESHOOTING.md`

Reemplaza las 2 apariciones de `init-db.sql` por `init-db.sh`. En la línea 78 aprox., reemplaza
`Verify the `n8n_user` credentials in your `.env` match what was created by `init-db.sql`.` por
`Verify `N8N_DB_PASSWORD` in your `.env` is the same value that existed when the postgres volume was first created (init-db.sh only runs on an empty volume; to re-run it, `docker compose down -v` deletes all data).`

## Paso 9 — `EXECUTION_PLAN.md`

- Línea 3: `Source of truth: `docker-compose.yml`, `init-db.sql`, `backend/`` → cambia `init-db.sql` por `init-db.sh`.
- En la sección "### 2. Remove hardcoded service passwords", cambia los dos `- [ ]` a `- [x]`.
  Debajo de cada uno agrega `  - Done (T11): <salida real de la verificación correspondiente>`.

## Paso 10 — `docs/RISK-ANALYSIS.md`

En la fila `DL-R04`, cambia Status de `**Observed, open**` a `**Observed → fixed**` y la columna
Fix de `T11` a `T11 (done)`. No toques otras filas.

## Verificación (desde `10-docker-compose-lab`)

1. `Select-String -Path *.yml, *.sh, *.md, .env.example, backend\src\*.py -Pattern "_secure_pass"`
   → **sin coincidencias** (no incluyas `secrets\`: no se lee).
2. `docker compose --env-file .env.example config -q` → sin salida y código 0 (`$LASTEXITCODE` = 0).
3. `py -3 scripts/sync_readme.py --check` → `README.md in sync`.
4. `py -3 -c "import sys; d=open('init-db.sh','rb').read(); sys.exit('CRLF found' if b'\r\n' in d else print('LF ok'))"` → `LF ok`.
5. `Select-String -Path README.md, TROUBLESHOOTING.md, EXECUTION_PLAN.md -Pattern "init-db\.sql"` → **sin coincidencias**.
6. **Opcional, solo si Docker Desktop está encendido** (`docker info` no da error):
   ```powershell
   Copy-Item .env.example .env
   docker compose up -d postgres
   Start-Sleep -Seconds 15
   docker compose exec postgres psql -U postgres -c "\l"
   docker compose down -v
   Remove-Item .env
   ```
   Esperado: la lista incluye `fastapi_db`, `n8n_db`, `grafana_db`. Si no hay Docker, escribe
   en el reporte `VERIFICACIÓN 6 NO EJECUTADA (sin Docker)`.

## Terminado cuando

Las verificaciones 1–5 pasan (y la 6 pasa o está explicada). Reporta y marca `T11` como `DONE`.
