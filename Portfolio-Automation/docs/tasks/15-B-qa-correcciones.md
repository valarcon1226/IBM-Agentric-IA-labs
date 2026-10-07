# 15-B · QA showcase: completar lo que faltó en 15-A

Carpeta: `Portfolio-Automation/15-qa-showcase` (solo esta). Spec original: `docs/tasks/15-A-qa-showcase.md`.
La revisión encontró huecos; corrígelos con la solución más simple que funcione (ponytail):

1. **Bugs falsos fuera.** QA-101 dio XPASS: problem_user sí agrega el morral, no es bug. Antes de
   escribir cada xfail, reprodúcelo a mano con Playwright. Bugs reales conocidos de problem_user a
   verificar: todas las imágenes del inventario son la misma; ordenar por precio/nombre no ordena;
   algunos botones "Add to cart" no funcionan (prueba los 6 productos); en checkout el apellido no
   queda escrito y sale "Last Name is required". Todo `xfail` con `strict=True` y el id del bug.
2. Comparación `standard_user` vs `problem_user` parametrizada (misma prueba, ambos usuarios).
3. Login inválido (contraseña errada y campos vacíos) con el mensaje exacto.
4. Inventario: ordenamiento (4 opciones) y quitar del carrito. Checkout: validaciones de formulario
   (nombre, apellido y código postal vacíos, cada uno con su mensaje) y total = suma + impuesto.
5. API negativos: token inválido en PUT/DELETE (403), id inexistente (404), POST con datos faltantes,
   y validación de esquema de las respuestas (claves y tipos). Máx. 1 petición/seg.
6. Versiones **fijas** (`==`) en `pyproject.toml` y `requirements.txt`; el CI las usa.
7. Resumen Markdown `reports/SUMMARY.md` generado por un hook en `tests/conftest.py`
   (totales, fallos, cada xfail con su bug).
8. `docs/BUG-REPORTS.md` y la matriz de `docs/TEST-PLAN.md` alineados con los bugs reales; evidencia =
   ruta real de una captura en `docs/evidence/` (tómala con Playwright).
9. Verifica: `.venv\Scripts\python.exe -m pytest tests` (0 XPASS, 0 fallos), `-m ruff check .`,
   `-m ruff format --check .`.

Reglas: sin commit ni push, sin `.env`, sin secretos, no toques otras carpetas, no pruebes otros
sitios. Si algo bloquea, detente y explícalo.
Al terminar escribe `docs/reviews/T-15-B.md` (español) con la salida real de cada comando.
