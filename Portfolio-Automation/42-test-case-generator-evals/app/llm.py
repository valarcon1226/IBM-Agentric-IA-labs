"""LLM abstractions: BaseLLM, OpenAILLM (Ollama compatible), and StubLLM."""

from __future__ import annotations

import json
import os
import re
from abc import ABC, abstractmethod
from typing import Any

import httpx


class BaseLLM(ABC):
    """Abstract base class for LLM backends."""

    @abstractmethod
    def complete(self, prompt: str, system_prompt: str | None = None) -> str:
        """Generate text completion from prompt and optional system prompt."""
        pass


class OpenAILLM(BaseLLM):
    """OpenAI-compatible client (e.g. Ollama via http://localhost:11434/v1)."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.base_url = (
            base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        ).rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL", "llama3.2")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "ollama")
        self.timeout = timeout if timeout is not None else float(os.getenv("LLM_TIMEOUT_S", "30"))

    def complete(self, prompt: str, system_prompt: str | None = None) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.0,
        }

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]["message"]
        return choice.get("content", "")


class StubLLM(BaseLLM):
    """Deterministic, rule-guided LLM for unit tests and harness self-evaluation."""

    def __init__(
        self,
        invalid_first: bool = False,
        always_fail: bool = False,
        canned_response: str | None = None,
    ) -> None:
        self.invalid_first = invalid_first
        self.always_fail = always_fail
        self.canned_response = canned_response
        self.call_count = 0

    def complete(self, prompt: str, system_prompt: str | None = None) -> str:
        self.call_count += 1

        if self.always_fail:
            return "ERROR: Malformed non-JSON response from failing model"

        if self.invalid_first and self.call_count == 1:
            return '{"test_cases": "invalid_structure_should_be_list"}'

        if self.canned_response is not None:
            return self.canned_response

        return self._generate_rule_based_response(prompt)

    def _generate_rule_based_response(self, prompt: str) -> str:
        """Generate deterministic test cases matching the requirement criteria."""
        req_id_match = re.search(r"REQ-\d+", prompt)
        req_id = req_id_match.group(0) if req_id_match else "REQ-00"

        # Check for specific golden requirements to guarantee exact criterion & regex alignment
        if req_id in STUB_RULES:
            cases = STUB_RULES[req_id]
            return json.dumps({"test_cases": cases}, indent=2, ensure_ascii=False)

        # Fallback for dynamic requirements in unit tests
        # Extract criterion IDs (e.g. AC-01, AC-02, ...)
        ac_ids = re.findall(r"(AC-\d+)", prompt)
        if not ac_ids:
            ac_ids = ["AC-01"]
        # De-duplicate preserving order
        seen = set()
        unique_acs = [x for x in ac_ids if not (x in seen or seen.add(x))]

        cases = [
            {
                "id": f"{req_id}-TC-01",
                "title": f"Verificación básica de {unique_acs[0]}",
                "level": "smoke",
                "preconditions": "Sistema operativo y usuario autenticado",
                "steps": [
                    "Navegar al módulo principal",
                    f"Ejecutar acción correspondiente al criterio {unique_acs[0]}",
                    "Verificar respuesta exitosa del sistema",
                ],
                "expected": f"Operación completada exitosamente cumpliendo {unique_acs[0]}",
                "covers": [unique_acs[0]],
            },
            {
                "id": f"{req_id}-TC-02",
                "title": "Validación funcional estándar del flujo",
                "level": "functional",
                "preconditions": "Datos de prueba precargados en base de datos",
                "steps": [
                    "Ingresar parámetros requeridos en el formulario",
                    "Confirmar la transacción con botón de envío",
                    "Inspeccionar registros generados",
                ],
                "expected": "El flujo se completa y persiste el estado esperado",
                "covers": unique_acs[:2],
            },
            {
                "id": f"{req_id}-TC-03",
                "title": "Manejo de error con datos no permitidos",
                "level": "negative",
                "preconditions": "Sesión activa en el aplicativo",
                "steps": [
                    "Introducir valores inválidos en campos obligatorios",
                    "Intentar procesar la solicitud",
                    "Observar mensaje de rechazo",
                ],
                "expected": "El sistema rechaza la operación y muestra mensaje de error",
                "covers": [unique_acs[-1]],
            },
            {
                "id": f"{req_id}-TC-04",
                "title": "Evaluación de condiciones límite y bordes",
                "level": "edge",
                "preconditions": "Entorno configurado en umbral máximo",
                "steps": [
                    "Establecer la carga en el valor extremo permitido",
                    "Disparar la ejecución simultánea",
                    "Comprobar integridad de límites",
                ],
                "expected": "El sistema opera de forma estable sin degradación ni desbordamiento",
                "covers": [unique_acs[0]],
            },
        ]
        return json.dumps({"test_cases": cases}, indent=2, ensure_ascii=False)


# Exact deterministic rule table for golden set (REQ-01 through REQ-12)
STUB_RULES: dict[str, list[dict[str, Any]]] = {
    "REQ-01": [
        {
            "id": "TC-01-01",
            "title": "Inicio de sesión exitoso con credenciales válidas",
            "level": "smoke",
            "preconditions": "Usuario registrado con email usuario@ejemplo.com y clave válida",
            "steps": [
                "Navegar a la pantalla de login",
                "Ingresar email usuario@ejemplo.com y contraseña correcta",
                "Hacer clic en Iniciar Sesión",
            ],
            "expected": "Redirección exitosa al dashboard principal con token de sesión activo",
            "covers": ["AC-01"],
        },
        {
            "id": "TC-01-02",
            "title": "Bloqueo temporal de cuenta tras superar intentos fallidos",
            "level": "negative",
            "preconditions": "Cuenta activa en la plataforma",
            "steps": [
                "Ingresar contraseña incorrecta consecutivamente durante 5 intentos",
                "Presionar Enviar en cada intento",
            ],
            "expected": "Se visualiza mensaje de cuenta bloqueada tras 5 intentos fallidos",
            "covers": ["AC-02"],
        },
        {
            "id": "TC-01-03",
            "title": "Expiración de enlace de recuperación de contraseña",
            "level": "edge",
            "preconditions": "Enlace de recuperación generado previamente",
            "steps": [
                "Esperar un lapso mayor a 15 minutos desde la generación",
                "Acceder al enlace de restablecimiento",
            ],
            "expected": "El enlace muestra error de token expirado por superar los 15 minutos",
            "covers": ["AC-03"],
        },
        {
            "id": "TC-01-04",
            "title": "Persistencia de sesión con casilla recordar activa",
            "level": "functional",
            "preconditions": "Navegador web limpio",
            "steps": [
                "Marcar la casilla recordar credenciales",
                "Autenticarse con éxito y reiniciar el navegador",
            ],
            "expected": "La cookie de persistencia mantiene la sesión iniciada sin pedir login",
            "covers": ["AC-04"],
        },
    ],
    "REQ-02": [
        {
            "id": "TC-02-01",
            "title": "Validación de formato de correo electrónico en registro",
            "level": "negative",
            "preconditions": "Formulario de registro abierto",
            "steps": [
                "Ingresar un correo sin dominio válido como 'usuario_sin_arroba'",
                "Intentar registrar la cuenta",
            ],
            "expected": "El sistema muestra advertencia de correo inválido por falta de @ y dominio",
            "covers": ["AC-01"],
        },
        {
            "id": "TC-02-02",
            "title": "Exigencia de longitud y caracteres especiales en contraseña",
            "level": "edge",
            "preconditions": "Pantalla de creación de cuenta",
            "steps": [
                "Probar contraseña con menos de 8 caracteres",
                "Probar contraseña válida con al menos 8 caracteres, número y símbolo especial",
            ],
            "expected": "Se valida requisito de al menos 8 caracteres con mayúscula y símbolo especial",
            "covers": ["AC-02"],
        },
        {
            "id": "TC-02-03",
            "title": "Rechazo de registro con correo ya existente",
            "level": "negative",
            "preconditions": "Correo cliente@ejemplo.com ya registrado en base de datos",
            "steps": [
                "Llenar formulario con cliente@ejemplo.com",
                "Enviar solicitud de registro",
            ],
            "expected": "Se presenta el error exacto: El correo ya está registrado",
            "covers": ["AC-03"],
        },
        {
            "id": "TC-02-04",
            "title": "Obligatoriedad de aceptación de términos y condiciones",
            "level": "functional",
            "preconditions": "Datos válidos ingresados",
            "steps": [
                "Desmarcar el checkbox de términos y condiciones",
                "Hacer clic en el botón Registrarse",
            ],
            "expected": "El sistema exige marcar la casilla de términos y condiciones para continuar",
            "covers": ["AC-04"],
        },
    ],
    "REQ-03": [
        {
            "id": "TC-03-01",
            "title": "Búsqueda por término clave en catálogo de productos",
            "level": "smoke",
            "preconditions": "Catálogo con productos indexados",
            "steps": [
                "Escribir término de búsqueda 'auriculares' en la barra",
                "Presionar tecla Enter",
            ],
            "expected": "El catálogo retorna lista con coincidencia de query en título o descripción",
            "covers": ["AC-01"],
        },
        {
            "id": "TC-03-02",
            "title": "Filtrado de productos por categoría seleccionada",
            "level": "functional",
            "preconditions": "Página de resultados con múltiples categorías",
            "steps": [
                "Seleccionar la categoría 'Electrónica' en el panel lateral",
                "Aplicar filtro de catálogo",
            ],
            "expected": "La vista actualiza mostrando únicamente productos pertenecientes a la categoría",
            "covers": ["AC-02"],
        },
        {
            "id": "TC-03-03",
            "title": "Filtrado por rango de precio mínimo y máximo",
            "level": "functional",
            "preconditions": "Listado de artículos con precios diversos",
            "steps": [
                "Establecer precio mínimo en 20 y precio máximo en 100",
                "Filtrar por rango de precio",
            ],
            "expected": "Los artículos mostrados cumplen el rango de precio entre mínimo y máximo",
            "covers": ["AC-03"],
        },
        {
            "id": "TC-03-04",
            "title": "Mensaje informativo ante búsqueda sin resultados",
            "level": "negative",
            "preconditions": "Barra de búsqueda accesible",
            "steps": [
                "Ingresar cadena aleatoria sin coincidencias 'xyz999abc'",
                "Ejecutar búsqueda",
            ],
            "expected": "Se muestra el mensaje amigable: No encontramos productos para la búsqueda",
            "covers": ["AC-04"],
        },
    ],
    "REQ-04": [
        {
            "id": "TC-04-01",
            "title": "Adición de producto al carrito según stock disponible",
            "level": "smoke",
            "preconditions": "Producto con stock disponible de 10 unidades",
            "steps": [
                "Seleccionar cantidad de 2 unidades",
                "Hacer clic en agregar al carrito",
            ],
            "expected": "El ítem se incorpora exitosamente respetando el stock disponible",
            "covers": ["AC-01"],
        },
        {
            "id": "TC-04-02",
            "title": "Recálculo automático del total al variar cantidades",
            "level": "functional",
            "preconditions": "Carrito con 1 producto agregado a $15 USD",
            "steps": [
                "Incrementar unidades de 1 a 3 en el selector",
                "Esperar recálculo automático",
            ],
            "expected": "El subtotal y total actualizado reflejan el nuevo monto tras recalcular",
            "covers": ["AC-02"],
        },
        {
            "id": "TC-04-03",
            "title": "Bloqueo al solicitar cantidad mayor al inventario",
            "level": "negative",
            "preconditions": "Producto con únicamente 3 unidades en stock",
            "steps": [
                "Ingresar manualmente cantidad 10 en el carrito",
                "Intentar actualizar el pedido",
            ],
            "expected": "Se visualiza alerta de stock insuficiente indicando el máximo disponible",
            "covers": ["AC-03"],
        },
        {
            "id": "TC-04-04",
            "title": "Eliminación de producto y actualización de contador",
            "level": "edge",
            "preconditions": "Carrito con un solo producto",
            "steps": [
                "Pulsar el botón eliminar ítem",
                "Confirmar remoción",
            ],
            "expected": "El producto se logra quitar y el contador del carrito vuelve a cero",
            "covers": ["AC-04"],
        },
    ],
    "REQ-05": [
        {
            "id": "TC-05-01",
            "title": "Aplicación de cupón de descuento porcentual vigente",
            "level": "smoke",
            "preconditions": "Carrito con productos elegibles por valor de $80 USD",
            "steps": [
                "Ingresar código de cupon válido 'PROMO10'",
                "Presionar botón Aplicar cupón",
            ],
            "expected": "Se aplica el porcentaje de descuento y disminuye el valor a pagar",
            "covers": ["AC-01"],
        },
        {
            "id": "TC-05-02",
            "title": "Rechazo de cupón con fecha vencida",
            "level": "negative",
            "preconditions": "Código promocional vencido el mes pasado",
            "steps": [
                "Ingresar el código vencido en el carrito",
                "Hacer clic en Aplicar",
            ],
            "expected": "Se despliega el mensaje de error: Cupón expirado o no vigente",
            "covers": ["AC-02"],
        },
        {
            "id": "TC-05-03",
            "title": "Control de monto mínimo de compra para descuento",
            "level": "edge",
            "preconditions": "Cupón condicionado a compra mínima de 50 USD",
            "steps": [
                "Intentar aplicar cupón con carrito de $35 USD",
                "Aumentar productos hasta sumar 50 USD o más",
            ],
            "expected": "El sistema exige compra mínima de 50 USD para activar el beneficio",
            "covers": ["AC-03"],
        },
        {
            "id": "TC-05-04",
            "title": "Impedimento de reutilización en cupón de un solo uso",
            "level": "functional",
            "preconditions": "Cupón de un solo uso previamente canjeado por el cliente",
            "steps": [
                "Digitar nuevamente el código promocional en un nuevo pedido",
                "Enviar validación",
            ],
            "expected": "El sistema notifica que el código ya utilizado era de un solo uso",
            "covers": ["AC-04"],
        },
    ],
    "REQ-06": [
        {
            "id": "TC-06-01",
            "title": "Validación de tarjeta de crédito con 16 dígitos",
            "level": "smoke",
            "preconditions": "Paso de pago en proceso de compra",
            "steps": [
                "Ingresar número de tarjeta de 16 dígitos",
                "Seleccionar fecha de vencimiento futura",
            ],
            "expected": "Se valida tarjeta y fecha de vencimiento sin arrojar advertencias",
            "covers": ["AC-01"],
        },
        {
            "id": "TC-06-02",
            "title": "Verificación estricta de código de seguridad CVV",
            "level": "functional",
            "preconditions": "Formulario de pago con tarjeta",
            "steps": [
                "Probar CVV con 2 dígitos (inválido)",
                "Probar CVV con 3 o 4 dígitos según franquicia",
            ],
            "expected": "El campo cvv exige con exactitud 3 o 4 dígitos numéricos",
            "covers": ["AC-02"],
        },
        {
            "id": "TC-06-03",
            "title": "Mecanismo de reintento automático por timeout de pasarela",
            "level": "edge",
            "preconditions": "Pasarela de pago simulando respuesta tardía",
            "steps": [
                "Generar solicitud de cobro con latencia alta",
                "Monitorear reintento tras timeout",
            ],
            "expected": "El sistema maneja el timeout realizando hasta 2 veces el reintento de conexión",
            "covers": ["AC-03"],
        },
        {
            "id": "TC-06-04",
            "title": "Generación de número de orden y confirmación por correo",
            "level": "functional",
            "preconditions": "Pago aprobado por el banco",
            "steps": [
                "Finalizar la transacción de compra",
                "Consultar la pantalla de confirmación y bandeja de entrada",
            ],
            "expected": "Se visualiza orden creada con formato ORD-12345 y llega correo de confirmación",
            "covers": ["AC-04"],
        },
    ],
    "REQ-07": [
        {
            "id": "TC-07-01",
            "title": "Validación de formato de código postal de 5 dígitos",
            "level": "functional",
            "preconditions": "Formulario de registro de direcciones",
            "steps": [
                "Ingresar código postal numérico de 5 dígitos",
                "Guardar dirección de entrega",
            ],
            "expected": "El código postal es aceptado al ajustarse al patrón de 5 dígitos",
            "covers": ["AC-01"],
        },
        {
            "id": "TC-07-02",
            "title": "Asignación de dirección predeterminada de envío",
            "level": "smoke",
            "preconditions": "Usuario con dos direcciones guardadas",
            "steps": [
                "Marcar la opción dirección predeterminada en la segunda dirección",
                "Confirmar cambios en perfil",
            ],
            "expected": "La dirección marcada queda como dirección predeterminada por defecto",
            "covers": ["AC-02"],
        },
        {
            "id": "TC-07-03",
            "title": "Restricción de cupo máximo de 5 direcciones por cuenta",
            "level": "edge",
            "preconditions": "Usuario con 5 direcciones ya registradas",
            "steps": [
                "Intentar agregar una sexta dirección en la libreta",
                "Enviar formulario",
            ],
            "expected": "El sistema frena la acción e informa el límite de 5 direcciones registradas",
            "covers": ["AC-03"],
        },
        {
            "id": "TC-07-04",
            "title": "Sanitización contra inyección de scripts en dirección",
            "level": "negative",
            "preconditions": "Campo de texto de calle habilitado",
            "steps": [
                "Introducir cadena '<script>alert(1)</script>' en la dirección",
                "Guardar información",
            ],
            "expected": "El sistema rechaza o sanitiza caracteres inválidos evitando inyección de código",
            "covers": ["AC-04"],
        },
    ],
    "REQ-08": [
        {
            "id": "TC-08-01",
            "title": "Control del plazo máximo de 30 días para devolución",
            "level": "edge",
            "preconditions": "Pedido entregado hace 35 días",
            "steps": [
                "Solicitar reembolso en el panel de mis pedidos",
                "Comprobar validación de fecha de entrega",
            ],
            "expected": "Se rechaza la solicitud por superar los 30 días hábiles desde la fecha de entrega",
            "covers": ["AC-01"],
        },
        {
            "id": "TC-08-02",
            "title": "Requerimiento de foto adjunta para producto dañado",
            "level": "functional",
            "preconditions": "Devolución por concepto de daño de fábrica",
            "steps": [
                "Seleccionar motivo de daño sin adjuntar imagen",
                "Adjuntar evidencia fotográfica en formato JPG",
            ],
            "expected": "El formulario exige adjuntar imagen o foto clara del daño como evidencia",
            "covers": ["AC-02"],
        },
        {
            "id": "TC-08-03",
            "title": "Selección de método de reembolso o crédito en tienda",
            "level": "smoke",
            "preconditions": "Devolución aprobada por el área de soporte",
            "steps": [
                "Elegir entre crédito en tienda o reintegro al método original",
                "Confirmar preferencia de reembolso",
            ],
            "expected": "El reembolso se programa hacia el método original o crédito en tienda según elección",
            "covers": ["AC-03"],
        },
        {
            "id": "TC-08-04",
            "title": "Exclusión de devolución en artículos de higiene personal",
            "level": "negative",
            "preconditions": "Pedido con prendas de ropa interior o higiene",
            "steps": [
                "Intentar radicar devolución para artículo clasificado en higiene",
                "Enviar requerimiento",
            ],
            "expected": "El sistema indica que el artículo de higiene no admite devolución por política",
            "covers": ["AC-04"],
        },
    ],
    "REQ-09": [
        {
            "id": "TC-09-01",
            "title": "Transición de estados de orden en tiempo real",
            "level": "smoke",
            "preconditions": "Orden registrada en la plataforma",
            "steps": [
                "Monitorear orden desde estado inicial",
                "Avanzar estados: en preparación, enviado y entregado",
            ],
            "expected": "La interfaz actualiza ordenadamente mostrando en preparación, enviado o entregado",
            "covers": ["AC-01"],
        },
        {
            "id": "TC-09-02",
            "title": "Visualización de enlace de rastreo de courier",
            "level": "functional",
            "preconditions": "Orden con estado Enviado y guía asignada",
            "steps": [
                "Abrir detalle del pedido enviado",
                "Hacer clic en el enlace de la empresa transportadora",
            ],
            "expected": "Se muestra el enlace de rastreo con número de guía válido hacia el courier",
            "covers": ["AC-02"],
        },
        {
            "id": "TC-09-03",
            "title": "Cancelación de pedido restringida a etapa de preparación",
            "level": "edge",
            "preconditions": "Orden en fase de preparación de despacho",
            "steps": [
                "Presionar botón Cancelar orden mientras está en preparación",
                "Intentar cancelar cuando la orden pase a Enviado",
            ],
            "expected": "La cancelación es admitida únicamente durante la etapa en preparación",
            "covers": ["AC-03"],
        },
        {
            "id": "TC-09-04",
            "title": "Validación ante número de guía inexistente",
            "level": "negative",
            "preconditions": "Página pública de consulta de envíos",
            "steps": [
                "Consultar un número de seguimiento con guía inválida 'TRACK-999999'",
                "Pulsar Buscar paquete",
            ],
            "expected": "El sistema responde: Número de seguimiento no encontrado",
            "covers": ["AC-04"],
        },
    ],
    "REQ-10": [
        {
            "id": "TC-10-01",
            "title": "Adición de producto a lista de deseos desde catálogo",
            "level": "smoke",
            "preconditions": "Usuario con sesión iniciada navegando el catálogo",
            "steps": [
                "Hacer clic en el icono de corazón en la ficha de producto",
                "Verificar confirmación visual",
            ],
            "expected": "El producto se logra agregar a la lista de deseos o wishlist",
            "covers": ["AC-01"],
        },
        {
            "id": "TC-10-02",
            "title": "Transferencia de ítem de lista de deseos al carrito",
            "level": "functional",
            "preconditions": "Lista de deseos con 1 producto guardado",
            "steps": [
                "Hacer clic en el botón mover al carrito",
                "Verificar inventario del carrito y la lista",
            ],
            "expected": "La acción permite mover al carrito el artículo y removerlo de la lista",
            "covers": ["AC-02"],
        },
        {
            "id": "TC-10-03",
            "title": "Configuración de privacidad pública y privada en lista",
            "level": "functional",
            "preconditions": "Lista de deseos configurada en modo privado",
            "steps": [
                "Cambiar visibilidad a lista pública",
                "Copiar el enlace compartible y abrirlo en ventana privada",
            ],
            "expected": "La lista pública genera un enlace compartible accesible para terceros",
            "covers": ["AC-03"],
        },
        {
            "id": "TC-10-04",
            "title": "Tope máximo de 100 artículos en la lista de deseos",
            "level": "edge",
            "preconditions": "Wishlist con exactamente 100 artículos",
            "steps": [
                "Intentar agregar el artículo número 101",
                "Observar validación del sistema",
            ],
            "expected": "Se aplica el límite de 100 artículos impidiendo adiciones adicionales",
            "covers": ["AC-04"],
        },
    ],
    "REQ-11": [
        {
            "id": "TC-11-01",
            "title": "Calificación numérica de 1 a 5 estrellas para productos",
            "level": "smoke",
            "preconditions": "Producto entregado a cliente",
            "steps": [
                "Seleccionar 4 estrellas en la escala visual",
                "Enviar puntuación",
            ],
            "expected": "El sistema registra calificación válida en el rango de 1 a 5 estrellas",
            "covers": ["AC-01"],
        },
        {
            "id": "TC-11-02",
            "title": "Control de extensión de reseña entre 10 y 1000 caracteres",
            "level": "edge",
            "preconditions": "Formulario de comentario abierto",
            "steps": [
                "Intentar enviar reseña con 5 caracteres (menos del mínimo 10)",
                "Redactar reseña descriptiva respetando entre 10 y 1000 caracteres",
            ],
            "expected": "El validador exige cumplir la longitud entre 10 y 1000 caracteres",
            "covers": ["AC-02"],
        },
        {
            "id": "TC-11-03",
            "title": "Distintivo de comprador verificado en opiniones",
            "level": "functional",
            "preconditions": "Reseña emitida por usuario que compró el producto",
            "steps": [
                "Publicar opinión de compra confirmada",
                "Visualizar publicación en el muro de reseñas",
            ],
            "expected": "Aparece la etiqueta distintiva de comprador verificado junto al autor",
            "covers": ["AC-03"],
        },
        {
            "id": "TC-11-04",
            "title": "Filtro de moderación contra lenguaje inapropiado",
            "level": "negative",
            "preconditions": "Editor de reseñas activo",
            "steps": [
                "Ingresar palabras ofensivas o groserías en el cuerpo de la reseña",
                "Pulsar Publicar",
            ],
            "expected": "El filtro de lenguaje inapropiado bloquea el envío y alerta al usuario",
            "covers": ["AC-04"],
        },
    ],
    "REQ-12": [
        {
            "id": "TC-12-01",
            "title": "Suscripción para alerta de reposición de producto agotado",
            "level": "smoke",
            "preconditions": "Producto con stock en 0",
            "steps": [
                "Hacer clic en el botón notificar cuando haya stock",
                "Digitar correo para recibir el aviso",
            ],
            "expected": "El sistema confirma suscripción para notificar cuando haya stock",
            "covers": ["AC-01"],
        },
        {
            "id": "TC-12-02",
            "title": "Disparo de correo de alerta tras reposición de inventario",
            "level": "functional",
            "preconditions": "Ingreso de nuevas existencias al almacén",
            "steps": [
                "Actualizar inventario del artículo",
                "Verificar cola de correos dentro de los siguientes 10 minutos",
            ],
            "expected": "La alerta de reposición se envía en un plazo no mayor a 10 minutos tras el restock",
            "covers": ["AC-02"],
        },
        {
            "id": "TC-12-03",
            "title": "Enlace de cancelación de suscripción en el correo",
            "level": "functional",
            "preconditions": "Correo de alerta recibido en bandeja",
            "steps": [
                "Abrir mensaje de notificación",
                "Hacer clic en el enlace cancelar suscripción",
            ],
            "expected": "El enlace unsubscribe remueve de inmediato el correo de la lista activa",
            "covers": ["AC-03"],
        },
        {
            "id": "TC-12-04",
            "title": "Prevención de alertas duplicadas para mismo usuario y producto",
            "level": "negative",
            "preconditions": "Usuario con alerta activa en producto agotado",
            "steps": [
                "Reintentar registrar el mismo correo en el mismo ítem",
                "Enviar formulario",
            ],
            "expected": "Se notifica al usuario que ya está suscrito evitando suscripción duplicada",
            "covers": ["AC-04"],
        },
    ],
}
