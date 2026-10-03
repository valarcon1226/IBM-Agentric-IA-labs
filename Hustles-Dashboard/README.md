# Hustles Dashboard

Panel de 3 pestañas (Vacantes / Freelance / Trend Spotter) que lee en vivo la base
`jobs.db` producida por los agentes del proyecto `jobHunter` (scout_agent, tailor_agent,
freelance_hunter_agent, trend_spotter_agent). Es un proyecto independiente — no importa
código ni modifica nada de `jobHunter/` ni de `Homelab/`, solo lee la misma base de datos.

## Estructura

```
Hustles-Dashboard/
  app.py              # backend FastAPI: sirve la UI y expone /api/jobs, /api/freelance, /api/trends
  requirements.txt
  Dockerfile
  docker-compose.yml
  static/
    index.html         # frontend de una sola página (fetch a la API, sin build step)
  data/
    jobs.db            # (no versionado) copia/enlace de la base de datos real
```

## Correr en local (smoke test)

```bash
pip install -r requirements.txt

# Windows (PowerShell) — apunta directo a la DB real del proyecto jobHunter:
$env:JOBS_DB_PATH = "..\jobHunter\jobs.db"
uvicorn app:app --reload --port 8100

# o con Docker:
docker compose up --build
```

Abre `http://localhost:8100`. Si `JOBS_DB_PATH` no apunta a un archivo válido, las tres
pestañas simplemente muestran 0 resultados (no truena) — revisa `/api/health` para
confirmar qué ruta está usando y si la encontró.

## Desplegar en el home server

El servidor (Debian, `192.168.2.12`, usuario SSH `valentina`) ya corre un stack de
Docker Compose en `~/homelab/`. Dos formas de sumar este servicio:

1. **Standalone**: copia esta carpeta completa al servidor (`scp`/`rsync` o `git clone`
   si la subes a un repo) y corre `docker compose up -d --build` dentro de ella. Queda
   escuchando en el puerto `8100`.
2. **Integrado al stack existente**: copia solo el bloque `hustles-dashboard` de
   `docker-compose.yml` dentro de `~/homelab/docker-compose.yml`, ajustando `build:` a la
   ruta donde quede esta carpeta en el server, y corre `docker compose up -d --build`
   desde `~/homelab/`.

No tengo acceso SSH a `192.168.2.12` — estos pasos los corres tú manualmente.

## Cómo mantener jobs.db actualizado

El `jobs.db` real lo generan los agentes de `jobHunter` corriendo en tu PC Windows, pero
el contenedor vive en el home server — hace falta un puente entre los dos. Dos opciones,
sin implementar ninguna todavía:

- **(a) Vía Nextcloud**, que ya corre en ese mismo servidor: agrega `jobs.db` a una
  carpeta sincronizada por el cliente de Nextcloud en tu PC, y apunta `JOBS_DB_PATH` a la
  ruta donde esa carpeta se sincroniza dentro del servidor (montada como volumen en el
  contenedor). Es la opción más simple porque reutiliza infraestructura que ya tienes.
- **(b) Vía scp/rsync programado**: una tarea programada en Windows (o un cron si
  migras los agentes al server más adelante) que haga `scp jobs.db
  valentina@192.168.2.12:~/homelab/hustles-dashboard/data/jobs.db` cada cierto tiempo.
  Más control fino sobre la frecuencia, pero un paso extra que mantener.

## Acceso remoto ("desde cualquier lugar")

Para no exponer el servicio directamente a internet, la vía estándar dado tu homelab
actual es una VPN personal (WireGuard) de vuelta a tu red local; una vez conectado,
`http://192.168.2.12:8100` funciona igual que en casa. Configurar esa VPN es un paso
aparte, no incluido en este proyecto.
