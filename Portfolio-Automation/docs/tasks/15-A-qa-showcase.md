# 15-A · QA showcase: plan, suite de regresión UI + API y reporte de bugs

Proyecto freelance #8 (`jobHunter/PORTFOLIO_PLAN.md` §2.8). Carpeta nueva:
`Portfolio-Automation/15-qa-showcase` (ya tiene `.venv` con Python 3.12). Objetivo: demostrar el
trabajo de una QA senior sobre aplicaciones **hechas para practicar pruebas**, que permiten
automatización: **SauceDemo** (https://www.saucedemo.com, tienda; trae usuarios con bugs a propósito,
como `problem_user` y `performance_glitch_user`) y **Restful Booker** (https://restful-booker.herokuapp.com,
API de reservas). No pruebes ningún otro sitio. Nada de carga ni estrés: máximo 1 petición por segundo.

1. `docs/TEST-PLAN.md` (español): alcance, fuera de alcance, riesgos, tipos de prueba, criterios de
   entrada/salida, entornos, matriz de trazabilidad requisito → caso → prueba automatizada.
2. Suite UI con **Playwright + pytest** (versiones fijas), patrón Page Object, datos de prueba
   separados del código: login (válido, bloqueado, inválido), inventario y orden, carrito,
   checkout completo con validaciones de formulario, y comparación de `standard_user` contra
   `problem_user` que **detecta** sus bugs (las pruebas que encuentran un bug conocido van
   marcadas `xfail` con el id del bug). Capturas y trace de Playwright cuando una prueba falla.
3. Suite API con **pytest + httpx** sobre Restful Booker: auth, CRUD de reservas, validación de
   esquema de respuesta, casos negativos (token inválido, datos faltantes, ids inexistentes).
   Además, la **colección de Postman** equivalente en `postman/` y cómo correrla con Newman.
4. Reportes: `pytest-html` autocontenido en `reports/`, y un resumen en Markdown generado al final
   (totales, fallos, xfail con su bug).
5. `docs/BUG-REPORTS.md`: cada bug encontrado en formato Jira (id, título, severidad, prioridad,
   entorno, pasos, esperado, obtenido, evidencia con la ruta de la captura). Solo bugs reales que
   las pruebas reproducen.
6. CI: `.github/workflows/qa.yml` **dentro de la carpeta del proyecto** (como plantilla, no en la raíz
   del repo) que instala dependencias y navegadores, corre ambas suites y sube el reporte como artefacto.
7. `README.md` en español para un cliente: qué hago como QA, qué entrega este proyecto, cómo correrlo,
   capturas como placeholder. Y `pyproject.toml` con ruff.
8. Verifica de verdad: `.venv\Scripts\python.exe -m playwright install chromium`, corre ambas suites,
   `-m ruff check .`, `-m ruff format --check .`. Pega la salida real.

Reglas: la solución más simple que funcione. Sin commit ni push. Sin secretos (las credenciales de
SauceDemo y Restful Booker son públicas y de prueba: van en un archivo de datos con un comentario que
lo aclara). Sin archivos temporales fuera de `reports/` (ignóralo en `.gitignore`). No toques otros
proyectos. Si algo te bloquea, detente y explícalo.
Al terminar escribe `docs/reviews/T-15-A.md` (español) con la salida real de cada comando.
