# Mi Homelab

Servidor personal en Debian que corre mis apps y automatizaciones 24/7. Última actualización: **2026-09-28**.

## Propósito

Desde el 2026-09-28 el homelab está dedicado **solo a apps, automatizaciones y modelos locales**.
Los servicios de medios se retiraron en septiembre de 2026 para liberar disco (ver [Historial](#historial)).

## Datos del servidor

| Dato | Valor |
| :--- | :--- |
| Hostname | `homeLab1` |
| Sistema operativo | Debian GNU/Linux 13 (trixie), modo servidor, sin suspensión |
| IP local | `192.168.1.15` (antes `192.168.2.12`; **pendiente reservarla en el router por DHCP**) |
| Usuario SSH | `valentina` → `ssh valentina@192.168.1.15` |
| CPU / RAM | 8 núcleos / 7.6 GB |
| GPU | NVIDIA GeForce GTX 1050, 4 GB VRAM |
| Disco raíz | 211 GB (`/dev/sda2`), 35 GB usados (18%) al 2026-09-28 |

## Servicios activos

| Servicio | Puerto | URL | Qué es | Dónde se define |
| :--- | :--- | :--- | :--- | :--- |
| **Homepage** | `3000` | http://192.168.1.15:3000 | Panel principal | `~/homelab/docker-compose.yml` |
| **Portainer** | `9000` | http://192.168.1.15:9000 | Administración gráfica de Docker | `~/homelab/docker-compose.yml` |
| **Nextcloud** | `8443` | https://192.168.1.15:8443 | Almacenamiento de archivos privado | `~/homelab/docker-compose.yml` |
| **Hustles Dashboard** | `8100` | http://192.168.1.15:8100 | Dashboard en vivo de jobHunter | `~/homelab/hustles-dashboard/` |
| **Hermes** | `8642`, `9119` | — | Agente Hermes (Nous Research) con la biblioteca de Obsidian | `docker run` suelto (sin compose) |
| **jobHunter** (4 servicios) | — | — | Pipeline de búsqueda de empleo y freelance | `~/homelab/jobhunter/docker-compose.yml` |
| **Ollama** | `11434` | solo `localhost` | LLM local | servicio systemd `ollama` |

## jobHunter

Pipeline 24/7 en `~/homelab/jobhunter`. Los 4 servicios usan la imagen `jobhunter:latest`, `network_mode: host` (para llegar a Ollama en `localhost:11434`) y el código montado en `/app`. Guardan todo en `jobs.db` (SQLite).

| Servicio | Qué hace | Frecuencia |
| :--- | :--- | :--- |
| `scout` | Busca vacantes con JobSpy (LinkedIn, Indeed, Glassdoor), filtra seniors y las puntúa | cada 6 h (`SCOUT_INTERVAL_HOURS`) |
| `tailor` | Watchdog: arma el CV por arquetipo para cada vacante `Aprobado` | continuo (revisa cada 5 min) |
| `freelance` | Gigs de Freelancer.com y bounties de GitHub (Algora) | cada 12 h por defecto; el `.env` lo baja a 6 h (`FREELANCE_INTERVAL_HOURS`) |
| `trends` | Detecta tendencias de demanda freelance (tabla `market_trends`) | cada 24 h, arranca 1 h tarde para no competir por la GPU |

**Proveedores LLM** (en `.env`, con fallback en `llm_chain.py`): Gemini → Groq → Cerebras → OpenRouter → Ollama local. Si todos se quedan sin cuota, el agente se detiene de forma segura en vez de descartar vacantes por error.

Tablas de `jobs.db` al 2026-09-28: `jobs` (222), `freelance_gigs` (547), `market_trends` (49), `llm_usage_events`.

## LLM local (Ollama)

- **Versión:** Ollama 0.33.3, corriendo como servicio systemd.
- **Modelos:** `qwen3:4b` (principal; ~22.6 tok/s, 100% en GPU) y `openhermes` (viejo, 4.1 GB, candidato a borrar).
- **Escucha solo en `127.0.0.1:11434`.** jobHunter llega porque usa `network_mode: host`. Para usarlo desde la laptop u OmniRoute falta configurar `OLLAMA_HOST=0.0.0.0`.
- **Descartado por ahora:** Bonsai 2 27B de PrismML (5.9 GB, no cabe en 4 GB de VRAM y no funciona con Ollama). Reevaluar con una GPU de 8 GB o más (p. ej., RTX 3060 12 GB).
- **Opcional a probar:** Bonsai 8B 1-bit (~1.5 GB) con `llama-server`, comparado contra `qwen3:4b`.

Arquitectura propuesta:
```
automatizaciones → OmniRoute (API OpenAI) → 1º Ollama homelab (gratis)
                                          → 2º Groq / Gemini (fallback)
```

## Estructura de carpetas

```
~/homelab/
├── docker-compose.yml             # portainer, homepage, nextcloud
├── config/                        # configuración de cada app (~950 MB)
├── data/                          # datos de las apps (nextcloud)
├── jobhunter/                     # pipeline jobHunter (compose propio, jobs.db, CVs_Listos/)
├── hustles-dashboard/             # dashboard en el puerto 8100 (compose propio)
└── Library_Of_Alexandria/         # biblioteca que monta Hermes (RO / RW / _masks/private)
```

## Comandos útiles

```bash
ssh valentina@192.168.1.15
df -h /                                        # espacio en disco
docker ps                                      # qué está corriendo

cd ~/homelab && docker compose up -d           # levantar apps base
cd ~/homelab/jobhunter && docker compose ps    # estado de jobHunter
cd ~/homelab/jobhunter && docker compose logs --tail 50 scout
cd ~/homelab/jobhunter && docker compose restart

ollama list                                    # modelos locales
```

Para desplegar cambios de jobHunter: `scp archivo.py valentina@192.168.1.15:~/homelab/jobhunter/`. No hace falta rebuild salvo cambios en `requirements.txt` o `Dockerfile`.

## Historial

### 2026-09-28 — Disco lleno y retiro de los servicios de medios
- **Síntoma:** jobHunter detenido desde el 26 de septiembre con `database or disk is full`. El disco estaba al 100% (211G/211G).
- **Causa:** un servicio de medios con la configuración vacía se reinició el 24 de septiembre y llenó el disco en dos días.
- **Acciones:**
  1. Se retiraron los servicios de medios y sus datos.
  2. Se quitaron del `docker-compose.yml` base.
  3. Se reinició jobHunter.
- **Resultado:** disco al 18% (166G libres). scout, tailor, freelance y trends vuelven a guardar datos en `jobs.db`.
- **Lección:** el servidor queda reservado para automatizaciones hasta tener más almacenamiento, y falta una alerta de disco.

### 2026-09-24 — Cambio de IP
El servidor dejó de responder por SSH en `192.168.2.12`. Volvió a estar en línea con la IP `192.168.1.15`.

## Pendientes

1. Reservar `192.168.1.15` en el router (DHCP) para que la IP no vuelva a cambiar.
2. `docker logs` de `freelance` y `trends` no muestra nada desde el 26–27 de septiembre, aunque sí están corriendo (se ve en `jobs.db`). Probablemente sus archivos de log se dañaron con el disco lleno. Se arregla con `docker compose up -d --force-recreate freelance trends` (los hace correr de inmediato y gasta cuota LLM).
3. Glassdoor responde 403 a scout (LinkedIn e Indeed funcionan).
4. Ollama: configurar `OLLAMA_HOST=0.0.0.0` y `OLLAMA_KEEP_ALIVE=-1`, borrar `openhermes` y agregarlo como primer proveedor del combo `tailor-fallback` en OmniRoute.
5. Quitar la línea `version: '3.8'` de `~/homelab/docker-compose.yml` (Docker avisa que está obsoleta).
6. Hermes corre con `docker run` suelto; pasarlo a un compose para que sea reproducible.
7. Agregar una alerta de espacio en disco.
