# QA Showcase - Portfolio Automation

Bienvenido al repositorio **QA Showcase**, un portafolio de automatización que demuestra habilidades en pruebas de calidad, tanto para API como para UI.

## Descripción del Proyecto

Este repositorio contiene:
1. **Pruebas de API**: Utilizando `pytest` y `httpx` para validar los endpoints públicos de la aplicación Restful Booker.
2. **Documentación de QA**:
   - `docs/TEST-PLAN.md`: Un plan de pruebas detallado.
   - `docs/BUG-REPORTS.md`: Reportes de bugs en formato Jira simulando errores encontrados en SauceDemo.
3. **CI/CD**: Integración continua usando GitHub Actions para la ejecución de pruebas automáticas.

## Estructura del Repositorio

- `tests/api/`: Contiene los scripts de prueba de la API.
- `docs/`: Documentación del proceso de QA (Plan de Pruebas, Reportes de Bugs).
- `.github/workflows/`: Pipelines de CI/CD.

## Tecnologías Utilizadas

- **Python 3.10+**
- **Pytest**: Framework principal de pruebas.
- **Httpx**: Cliente HTTP para las peticiones a la API.
- **GitHub Actions**: Automatización y CI/CD.

## Instalación y Uso

1. Clonar este repositorio.
2. Crear un entorno virtual:
   ```bash
   python -m venv venv
   source venv/bin/activate  # En Windows: venv\Scripts\activate
   ```
3. Instalar las dependencias:
   ```bash
   pip install pytest httpx
   ```
4. Ejecutar las pruebas:
   ```bash
   pytest tests/api/ -v
   ```

## Contacto
Desarrollado para el portafolio de QA Automation.
