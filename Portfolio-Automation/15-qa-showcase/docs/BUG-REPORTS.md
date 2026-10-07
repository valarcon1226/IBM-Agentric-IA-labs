# Reportes de Bugs (Jira Format)

A continuacion se documentan defectos que se pueden encontrar durante la ejecucion de las pruebas, simulando los escenarios fallidos del `problem_user` en SauceDemo.

---

## [QA-102] Error al ordenar productos (problem_user)

**Project:** QA Showcase  
**Issue Type:** Bug  
**Status:** To Do  
**Priority:** High  
**Reporter:** Automation Team  
**Environment:** Chrome / Edge, Windows/Linux/macOS  
**Labels:** UI, Sorting, Problem-User  

### Description
Al iniciar sesion como `problem_user`, intentar ordenar los productos por precio o nombre no funciona.

### Steps to Reproduce
1. Navegar a https://www.saucedemo.com/
2. Iniciar sesion como `problem_user`.
3. Seleccionar la opcion para ordenar los productos.

### Expected Result
Los productos se ordenan correctamente.

### Actual Result
El ordenamiento no cambia el orden de los productos.

### Attachments
- `docs/evidence/qa-102.png`

---

## [QA-103] Errores visuales al cargar imagenes de productos

**Project:** QA Showcase  
**Issue Type:** Bug  
**Status:** To Do  
**Priority:** Medium  
**Reporter:** Automation Team  
**Environment:** Chrome / Edge, Windows/Linux/macOS  
**Labels:** UI, Visual, Problem-User  

### Description
Al iniciar sesion como `problem_user`, todas las imagenes de los productos muestran la misma imagen por defecto.

### Steps to Reproduce
1. Navegar a https://www.saucedemo.com/
2. Iniciar sesion como `problem_user`.

### Expected Result
Cada producto muestra su imagen correspondiente.

### Actual Result
Todos los productos muestran la misma imagen de un perro (`sl-404.jpg`).

### Attachments
- `docs/evidence/qa-103.png`

---

## [QA-104] Botones Add to cart que no funcionan

**Project:** QA Showcase  
**Issue Type:** Bug  
**Status:** To Do  
**Priority:** High  
**Reporter:** Automation Team  
**Environment:** Chrome / Edge, Windows/Linux/macOS  
**Labels:** UI, Cart, Problem-User  

### Description
Algunos botones "Add to cart" no funcionan para `problem_user`.

### Steps to Reproduce
1. Navegar a https://www.saucedemo.com/
2. Iniciar sesion como `problem_user`.
3. Intentar agregar todos los productos al carrito.

### Expected Result
Todos los botones agregan su respectivo producto al carrito.

### Actual Result
Algunos botones no reaccionan ni agregan el producto.

### Attachments
- `docs/evidence/qa-104.png`

---

## [QA-105] El apellido no queda escrito en el checkout

**Project:** QA Showcase  
**Issue Type:** Bug  
**Status:** To Do  
**Priority:** High  
**Reporter:** Automation Team  
**Environment:** Chrome / Edge, Windows/Linux/macOS  
**Labels:** UI, Checkout, Problem-User  

### Description
Al escribir el apellido en el formulario de checkout, el campo se borra y lanza el error "Error: Last Name is required".

### Steps to Reproduce
1. Iniciar sesion como `problem_user`.
2. Ir a checkout y rellenar el formulario.
3. Hacer clic en Continue.

### Expected Result
Avanzar a la pagina de resumen de checkout sin errores.

### Actual Result
Se muestra el error "Error: Last Name is required" y el campo Last Name queda vacio.

### Attachments
- `docs/evidence/qa-105.png`

## [QA-106] Error al quitar producto del carrito (problem_user)

**Project:** QA Showcase  
**Issue Type:** Bug  
**Status:** To Do  
**Priority:** High  
**Reporter:** Automation Team  
**Environment:** Chrome / Edge, Windows/Linux/macOS  
**Labels:** UI, Cart, Problem-User  

### Description
Al iniciar sesion como `problem_user` e intentar quitar un articulo del carrito haciendo clic en "Remove", el producto no se elimina.

### Steps to Reproduce
1. Iniciar sesion como `problem_user`.
2. Agregar un producto al carrito.
3. Hacer clic en "Remove".

### Expected Result
El producto se quita del carrito y desaparece el badge de cantidad.

### Actual Result
El producto permanece en el carrito.

### Attachments
- `docs/evidence/qa-106.png`
