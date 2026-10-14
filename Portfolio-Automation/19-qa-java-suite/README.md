# Suite de Automatización QA en Java (Proyecto 19)

Suite integral de pruebas automatizadas desarrollada en **Java 21**, diseñada para satisfacer los estándares técnicos y de arquitectura de un rol Senior de QA Automation. Cubre pruebas de interfaz de usuario (UI), pruebas de servicios web (API REST), pruebas basadas en comportamiento (BDD con Cucumber), reproducción controlada de defectos conocidos y generación de reportes ejecutivos interactivos con Allure.

---

## 🎯 Qué demuestra este proyecto

1. **Arquitectura modular y mantenible (Page Object Model - POM):**
   - Separación estricta entre lógica de interacción con la UI (`qa.ui.pages`) y assertions/flujos de prueba (`qa.ui.tests`).
   - Reutilización de componentes base para esperas explícitas y configuración de WebDriver.

2. **Automatización UI robusta con Selenium WebDriver 4 & Microsoft Edge:**
   - Pruebas E2E de inicio a fin: autenticación, catálogo, carrito de compras y checkout completo hasta confirmación de orden.
   - Validaciones estrictas de reglas de negocio y formulario (mensajes de error exactos y tolerancia matemática en cálculo de impuestos/totales).

3. **Automatización de APIs REST con RestAssured:**
   - Flujo CRUD completo contra la API de [Restful Booker](https://restful-booker.herokuapp.com): autenticación (`/auth`), creación, lectura, actualización (`PUT`/`PATCH`) y eliminación (`DELETE`).
   - Casos negativos exhaustivos (códigos HTTP 403 Forbidden por token inválido y 404 Not Found por recurso inexistente).
   - Control de tasa de peticiones (*rate limiting* preventivo: máximo 1 petición por segundo).

4. **BDD y especificación viva con Cucumber:**
   - Escenarios escritos en Gherkin (`saucedemo.feature`) vinculados con `RunCucumberTest` de JUnit Platform Suite.
   - Reutilización directa de los mismos Page Objects entre pruebas JUnit y pasos de Cucumber.

5. **Aislamiento y portabilidad con Docker:**
   - Ejecución sin dependencias locales de Java o Maven mediante contenedores independientes (`selenium/standalone-edge` y contenedor de ejecución `maven:3.9-eclipse-temurin-21`).

6. **Integración Continua (CI/CD) y Reportería Ejecutiva:**
   - Pipelines listos para GitHub Actions y Azure DevOps en la carpeta `ci/`.
   - Reporte interactivo Allure con historial, categorización de pruebas y capturas.

---

## 📋 Matriz de Casos de Prueba (35 Casos)

| ID | Tipo | Qué valida |
| :--- | :--- | :--- |
| **LOGIN-01** | UI (Selenium) | Login exitoso con usuario estándar (`standard_user`) y redirección a catálogo (`inventory.html`). |
| **LOGIN-02** | UI (Selenium) | Usuario bloqueado (`locked_out_user`) muestra mensaje `"Epic sadface: Sorry, this user has been locked out."`. |
| **LOGIN-03** | UI (Selenium) | Contraseña inválida muestra mensaje exacto de credenciales no coincidentes. |
| **LOGIN-04** | UI (Selenium) | Validaciones de obligatoriedad: mensajes exactos ante usuario vacío y contraseña vacía. |
| **INV-01** | UI (Selenium) | Agregar mochila al carrito, validar incremento del badge a "1", removerla y validar regreso a "0". |
| **INV-02** | UI (Selenium) | Selección y aplicación de los 4 criterios de ordenamiento en catálogo (Z-A, Low-High, High-Low, A-Z). |
| **QA-104** | UI / Bug Conocido | Con `problem_user`, tras pulsar *Add to cart* en los 6 productos el carrito no llega a 6 (algunos botones no hacen nada). |
| **QA-105** | UI / Bug Conocido | Reproducción controlada: campo *Last Name* no se persiste en checkout con `problem_user` y genera error. |
| **QA-106** | UI / Bug Conocido | Con `problem_user`, *Remove* en el inventario no quita la mochila: el carrito sigue en 1. |
| **CHECKOUT-01** | UI (Selenium) | Carrito con 2 productos (mochila y luz para bicicleta): verificación de badge en "2" y 2 filas en página de carrito. |
| **CHECKOUT-02** | UI (Selenium) | Checkout E2E completo: carrito con 2 items, llenado de datos, vista previa, finalización y header final `"Thank you for your order!"`. |
| **CHECKOUT-03** | UI (Selenium) | Validación de checkout: dejar campo First Name vacío muestra `"Error: First Name is required"`. |
| **CHECKOUT-04** | UI (Selenium) | Validación de checkout: dejar campo Last Name vacío muestra `"Error: Last Name is required"`. |
| **CHECKOUT-05** | UI (Selenium) | Validación de checkout: dejar campo Postal Code vacío muestra `"Error: Postal Code is required"`. |
| **CHECKOUT-06** | UI (Selenium) | Validación matemática: Total facturado es exactamente igual a `Subtotal + Impuesto` (tolerancia 0.01). |
| **CHECKOUT-07** | UI (Selenium) | Botón *Cancel* en Paso 1 de Checkout retorna correctamente a la vista del carrito (`cart.html`). |
| **CHECKOUT-08** | UI (Selenium) | Botón *Cancel* en Paso 2 de Checkout (Overview) retorna correctamente al catálogo (`inventory.html`). |
| **API-01** | API (RestAssured) | `POST /auth`: autenticación con credenciales de administrador retorna HTTP 200 y token no nulo. |
| **API-02** | API (RestAssured) | `POST /auth`: negativo con credenciales erradas devuelve HTTP 200 con `reason: "Bad credentials"`. |
| **API-03** | API (RestAssured) | `POST /booking`: creación de reserva retorna HTTP 200, genera un `bookingid` y replica los datos enviados. |
| **API-04** | API (RestAssured) | `GET /booking/{id}`: consulta de reserva creada previamente por ID retorna HTTP 200 y datos íntegros. |
| **API-05** | API (RestAssured) | `GET /booking`: consulta general devuelve listado de reservas con longitud mayor a 0. |
| **API-06** | API (RestAssured) | `PUT /booking/{id}`: actualización total de reserva con token retorna HTTP 200 y campos modificados. |
| **API-07** | API (RestAssured) | `DELETE /booking/{id}`: eliminación de reserva con token retorna HTTP 201; GET subsecuente valida HTTP 404. |
| **API-08** | API (RestAssured) | `PUT /booking/{id}` (Negativo): intento de actualización con token inválido retorna HTTP 403 Forbidden. |
| **API-09** | API (RestAssured) | `DELETE /booking/{id}` (Negativo): intento de eliminación con token inválido retorna HTTP 403 Forbidden. |
| **API-10** | API (RestAssured) | `GET /booking/999999999` (Negativo): consulta de reserva inexistente retorna HTTP 404 Not Found. |
| **API-11** | API (RestAssured) | `GET /ping`: verificación de disponibilidad de la API retorna HTTP 201 Created. |
| **BDD-01** | BDD (Cucumber) | Escenario bug QA-104: con `problem_user` el carrito no llega a 6 tras agregar los 6 productos. |
| **BDD-02** | BDD (Cucumber) | Escenario bug QA-105: imposibilidad de registrar apellido en checkout con `problem_user`. |
| **BDD-03** | BDD (Cucumber) | Escenario bug QA-106: con `problem_user` *Remove* en el inventario no quita el producto. |
| **BDD-04** | BDD (Cucumber) | Escenario estándar: usuario agrega 2 productos distintos y badge refleja "2". |
| **BDD-05** | BDD (Cucumber) | Escenario estándar: flujo E2E completo de compra hasta mensaje `"Thank you for your order!"`. |
| **BDD-06** | BDD (Cucumber) | Escenario validación: mensaje exacto ante nombre faltante en checkout. |
| **BDD-07** | BDD (Cucumber) | Escenario validación: mensaje exacto ante código postal faltante en checkout. |

---

## 🚀 Cómo ejecutar las pruebas con Docker

No es necesario instalar Java, Maven ni el navegador Edge localmente. Todo el entorno corre orquestado con Docker Compose.

### 1. Iniciar el servicio de Selenium Edge
```bash
docker compose up -d selenium
```

### 2. Ejecutar la suite completa de pruebas
```bash
docker compose run --rm tests mvn -q test
```
*Para ver el detalle de cada prueba en consola, ejecute:*
```bash
docker compose run --rm tests mvn test
```

### 3. Detener los contenedores al finalizar
```bash
docker compose down
```

---

## 📊 Generación y visualización del reporte Allure

El plugin oficial de Allure está integrado en `pom.xml`. Durante la ejecución de las pruebas se generan los archivos crudos en `target/allure-results`.

### 1. Generar el reporte HTML estático
Ejecute el siguiente comando con Docker:
```bash
docker compose run --rm tests mvn allure:report
```
El reporte HTML autónomo se generará automáticamente en:
```
19-qa-java-suite/target/site/allure-maven-plugin/
```

### 2. Abrir el reporte en el navegador
- Abra directamente con su navegador el archivo:
  `target/site/allure-maven-plugin/index.html`
- O si cuenta con la herramienta Allure CLI localmente:
  ```bash
  allure open target/site/allure-maven-plugin
  ```

---

## 🔄 Integración Continua (CI/CD)

En el directorio `ci/` se incluyen configuraciones listas para producción:

1. **GitHub Actions (`ci/github-actions.yml`):**
   - Levanta el contenedor de Selenium Edge en modo headless.
   - Ejecuta las pruebas mediante Docker.
   - Genera el reporte de Allure mediante `simple-elf/allure-report-action`.
   - Publica automáticamente el reporte web en GitHub Pages (`gh-pages`).

2. **Azure DevOps Pipelines (`ci/azure-pipelines.yml`):**
   - Orquesta el ciclo de vida de los contenedores Docker.
   - Ejecuta la suite de pruebas Maven.
   - Publica los resultados XML en formato JUnit (`PublishTestResults@2`) para integración en el panel de pruebas de Azure DevOps.
