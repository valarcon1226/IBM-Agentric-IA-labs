# T13-01 — Fase 3, ítems 4–6

- 4: `[x]` modelos Pydantic; `import app.models` → `models ok`; `pytest tests/test_models.py -q` → 2 passed.
- 5: `[x]` limpieza D5; `pytest tests/test_services.py -v` → 4 passed (3 filas README + motivos y normalización).
- 6: `[ ]` POST upload protegido por Bearer, almacenamiento MinIO y alta en uploads; fakes `pytest tests/test_routes.py -q` → 2 passed. Curl y consola MinIO pendientes: needs Docker (D7).
- Compuer tas del ítem 6: ruff check `All checks passed!`; format `14 files already formatted`; mypy `Success: no issues found in 8 source files`; pytest 10 passed, 1 failed, cobertura 94%. Único rojo previsto: tres rutas documentadas pendientes.
- README: cuatro `curl` llevan `Authorization: Bearer $API_KEY` y sección 12 incluye `API_KEY=change_me_api_key` (D4).
- `process_upload` es temporalmente un hook vacío: se implementa en el ítem 7; no afirmar procesamiento real hasta entonces.