import os
import subprocess
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
from database import get_approved_jobs
import llm_chain

# NOTA (2026-09-21): sin límite de reintentos a propósito — esto corre 24/7. tailor_agent.py ya
# no crashea cuando se agota el cupo gratis (llm_chain lleva una ventana móvil de 24h y corta
# limpio con resumen), así que este watchdog nunca "se rinde": si no hubo avance, calcula
# exactamente cuándo se libera el próximo hueco de cupo (en vez de un cooldown fijo a ciegas) y
# duerme hasta ahí, en trozos de máximo MAX_WAIT_CHUNK_SECONDS para poder re-chequear si el scout
# sumó vacantes nuevas mientras tanto. Se detiene solo con Ctrl+C o matando el proceso.
COOLDOWN_SECONDS = 10           # pausa corta cuando SÍ hubo avance, antes de seguir con la próxima
NO_PENDING_POLL_SECONDS = 300   # cada cuánto reescanear la DB cuando no hay nada 'Aprobado'
MAX_WAIT_CHUNK_SECONDS = 900    # nunca dormir más de 15 min de un tirón esperando cupo


def main():
    print("======================================================")
    print(" Watchdog 24/7: corre tailor_agent.py sin parar nunca.")
    print(" Si se agota el cupo gratis, espera el próximo hueco de")
    print(" la ventana móvil de 24h en vez de rendirse.")
    print("======================================================\n")

    while True:
        try:
            pending = len(get_approved_jobs())
        except Exception as e:
            print(f"[Watchdog] No pude leer jobs.db: {e}. Reintentando en {COOLDOWN_SECONDS}s...")
            time.sleep(COOLDOWN_SECONDS)
            continue

        if pending == 0:
            print(f"[Watchdog] No hay vacantes 'Aprobado' pendientes ahora mismo. "
                  f"Durmiendo {NO_PENDING_POLL_SECONDS}s y reescaneando (el scout puede sumar nuevas)...")
            time.sleep(NO_PENDING_POLL_SECONDS)
            continue

        print(f"\n[Watchdog] {pending} vacantes pendientes. Lanzando tailor_agent.py...\n")

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        result = subprocess.run(
            [sys.executable, "-u", "tailor_agent.py"],
            cwd=BASE_DIR,
            env=env
        )

        print(f"\n[Watchdog] tailor_agent.py terminó con código de salida {result.returncode}.")

        new_pending = len(get_approved_jobs())
        progress_made = new_pending < pending
        print(f"[Watchdog] Vacantes pendientes: {pending} -> {new_pending} "
              f"({'avanzó' if progress_made else 'SIN AVANCE en este intento'}).")

        if progress_made:
            print(f"[Watchdog] Esperando {COOLDOWN_SECONDS}s antes de seguir...")
            time.sleep(COOLDOWN_SECONDS)
            continue

        # Sin avance: lo más probable es que se haya agotado el cupo gratis a mitad de camino.
        wait_s = llm_chain.seconds_until_any_slot()
        if wait_s <= 0:
            # Había presupuesto disponible y aun así no avanzó -> no parece ser cupo (¿bug,
            # red caída, Playwright roto?). Pausa corta de seguridad, no martillar en loop apretado.
            print("[Watchdog] Había presupuesto disponible pero no hubo avance — no parece ser cupo "
                  "agotado, revisá el log de la corrida. Reintentando en 60s de todas formas...")
            wait_s = 60
        else:
            wait_s = min(wait_s, MAX_WAIT_CHUNK_SECONDS)
            print(f"[Watchdog] Sin avance — esperando {int(wait_s)}s hasta el próximo hueco de cupo...")
        llm_chain.print_budget_status()
        time.sleep(wait_s)


if __name__ == "__main__":
    main()
