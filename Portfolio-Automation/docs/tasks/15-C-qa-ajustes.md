# 15-C · QA showcase: últimos ajustes tras revisar 15-B

Carpeta: `Portfolio-Automation/15-qa-showcase` (solo esta). Solución más simple que funcione (ponytail).

1. **QA-105 no se ejecuta**: `tests/ui/test_checkout.py` llama `pytest.xfail("QA-105")` al inicio, así
   que la prueba nunca corre ni detecta el bug. Cámbialo a
   `pytest.param("problem", marks=pytest.mark.xfail(strict=True, reason="QA-105"))` como en
   `test_inventory.py`, y que la prueba falle por el bug real (apellido vacío / "Last Name is required").
2. Borra el fixture `setup` que solo hace `pass` en `test_checkout.py`.
3. Comparación de dinero con floats: `assert item_total + tax == total` es frágil. Usa
   `pytest.approx(total, abs=0.01)` o compara redondeando a 2 decimales.
4. Faltan las capturas `docs/evidence/qa-104.png`, `qa-105.png` y `qa-106.png` que cita
   `docs/BUG-REPORTS.md`. Tómalas con Playwright reproduciendo cada bug.
5. Verifica: `.venv\Scripts\python.exe -m pytest tests -rxX` (0 fallos, 0 XPASS, 5 xfail, y QA-105 debe
   aparecer como XFAIL con traceback real, no saltado), `-m ruff check .`, `-m ruff format --check .`.

Reglas: sin commit ni push, sin `.env`, sin secretos, no toques otras carpetas, no pruebes otros sitios.
Al terminar escribe `docs/reviews/T-15-C.md` (español) con la salida real de cada comando.
