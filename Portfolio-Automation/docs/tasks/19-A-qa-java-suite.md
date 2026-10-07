# 19-A · Suite de QA en Java: Selenium, RestAssured, Cucumber y CI

Carpeta nueva: `Portfolio-Automation/19-qa-java-suite` (solo esta). Imita vacantes de QA Automation que piden
"Java, Selenium, RestAssured, Cucumber/BDD, CI/CD, Azure DevOps" (Java es el gap #1 de QA en jobHunter).
Mismas apps y mismos defectos que `15-qa-showcase` (léelo: SauceDemo para UI, Restful Booker para API,
bugs QA-104/105/106 de `problem_user`) para que se puedan comparar.

1. Java 21 + Maven + JUnit 5. NO instales Java en la máquina: todo corre en Docker
   (`maven:3.9-eclipse-temurin-21`) contra `selenium/standalone-chrome` (RemoteWebDriver), con `docker-compose.yml`.
2. UI con Selenium 4 y Page Objects (login, inventario, carrito, checkout), esperas explícitas (nada de `sleep`),
   datos de prueba separados. Los bugs conocidos como pruebas que fallan a propósito y están marcadas (como el 15).
3. API con RestAssured: auth, CRUD de bookings, validación de esquema JSON, casos negativos.
4. Cucumber: 2–3 `.feature` en inglés (login, compra, booking) que reutilizan los Page Objects.
5. Reporte Allure (o el de Surefire si Allure complica) guardado en `reports/`, con capturas en las fallas.
6. CI: no toques `.github/` de la raíz del repo; deja `ci/github-actions.yml` y
   `ci/azure-pipelines.yml` listos para copiar, que corren `mvn test` en Docker y publican el reporte.
7. `README.md` en inglés: qué cubre, cómo correr (un solo comando), tabla de casos ↔ defectos, comparación corta con
   el 15 (Python) y capturas del reporte.

Verificación (salida real): `docker compose run --rm tests mvn -q test` (resumen de pasados/fallados/esperados),
ubicación del reporte generado, y al final `docker compose down`.

Reglas: ponytail, sin commit ni push, sin secretos, no toques otras carpetas.
Al terminar escribe `docs/reviews/T-19-A.md` (español) con la salida real de cada comando.
