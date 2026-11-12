# Plan de Pruebas (Test Plan)

## 1. Alcance (Scope)
El alcance de este proyecto de pruebas incluye la automatizaciÃ³n de flujos crÃ­ticos tanto de interfaz de usuario (UI) en el sitio web de demostraciÃ³n Swag Labs (SauceDemo) como pruebas de API (Backend) contra la aplicaciÃ³n Restful Booker. Se incluirÃ¡n validaciones de autenticaciÃ³n, gestiÃ³n de reservas en la API y flujos de compra en la UI.

## 2. Fuera de Alcance (Out of Scope)
- Pruebas de rendimiento y estrÃ©s.
- Pruebas de seguridad profundas y escaneo de vulnerabilidades.
- Pruebas en dispositivos mÃ³viles nativos.
- Pruebas de accesibilidad (WCAG).
- Otros servicios no especificados en los dominios de SauceDemo o Restful Booker.

## 3. Riesgos (Risks)
- **Riesgo:** Inestabilidad de las APIs pÃºblicas (Restful Booker) al estar alojadas en servidores gratuitos, pueden presentar latencia o tiempos de inactividad.
  **MitigaciÃ³n:** Configurar reintentos en los scripts automatizados y capturar errores de timeout.
- **Riesgo:** Cambios inesperados en los localizadores de la UI (SauceDemo).
  **MitigaciÃ³n:** Usar selectores robustos (por ejemplo, atributos de `data-test`) en lugar de rutas absolutas XPath.

## 4. Tipos de Pruebas (Test Types)
- **Pruebas Funcionales Automatizadas (UI):** Verificar que los flujos de inicio de sesiÃ³n y compras funcionan como se espera.
- **Pruebas de IntegraciÃ³n (API):** Comprobar que los endpoints de creaciÃ³n, lectura, actualizaciÃ³n y eliminaciÃ³n de reservas responden de forma adecuada y con los cÃ³digos HTTP correctos.
- **Pruebas de RegresiÃ³n:** EjecuciÃ³n mediante CI/CD ante cada cambio en el repositorio.

## 5. Criterios de Entrada y Salida (Entry/Exit Criteria)
### Criterios de Entrada
- Los entornos de SauceDemo y Restful Booker se encuentran disponibles.
- Los requisitos de los flujos principales estÃ¡n documentados.
- El repositorio estÃ¡ inicializado y las herramientas instaladas.

### Criterios de Salida
- El 100% de los casos de prueba planeados han sido automatizados y ejecutados.
- No existen defectos crÃ­ticos o de severidad alta abiertos en los flujos principales.
- El pipeline CI/CD en GitHub Actions ejecuta correctamente las pruebas.

## 6. Entornos (Environments)
- **Desarrollo/EjecuciÃ³n Local:** Windows/macOS, Python 3.10+, Pytest, Httpx.
- **CI/CD:** GitHub Actions (Ubuntu-latest).
- **Target UI:** https://www.saucedemo.com/
- **Target API:** https://restful-booker.herokuapp.com/

## 7. Matriz de Trazabilidad (Traceability Matrix)

| Req ID | Descripcion | Caso de Prueba | Tipo de Prueba | Estado |
|--------|-------------|----------------|----------------|--------|
| REQ-01 | Usuario puede hacer Login | test_login_success | UI | Planeado |
| REQ-02 | Usuario puede añadir producto | test_add_to_cart | UI | Planeado |
| REQ-03 | Generar token de autenticacion API | test_auth_token | API | Completado |
| REQ-04 | Crear una reserva | test_create_booking | API | Completado |
| REQ-05 | Leer una reserva por ID | test_get_booking | API | Completado |
| REQ-06 | Actualizar una reserva | test_update_booking | API | Completado |
| REQ-07 | Eliminar una reserva | test_delete_booking | API | Completado |
| BUG-102 | Ordenar productos | test_inventory_sorting | UI | Planeado |
| BUG-103 | Imagenes correctas | test_inventory_images | UI | Planeado |
| BUG-104 | Botones Add to Cart | test_add_to_cart | UI | Planeado |
| BUG-105 | Checkout apellido | test_checkout_form | UI | Planeado || BUG-106 | Quitar producto del carrito | test_remove_item_from_cart | UI | Planeado |
