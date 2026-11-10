"""MCP Server for Sabor de Casa restaurant assistant.

Exposes tools for menu, schedules, reservations, order status, delivery zones,
and a resource containing all operational policies.
"""

from __future__ import annotations

import argparse
import sys
import unicodedata

from mcp.server.mcpserver import MCPServer
from pydantic import ValidationError

from app.db import crear_reserva_db, init_db, obtener_pedido_db
from app.knowledge import (
    load_all_policies,
    parse_delivery_zones,
    parse_menu,
)
from app.models import (
    ConsultarHorarioInput,
    ConsultarMenuInput,
    CrearReservaInput,
    EstadoPedidoInput,
    ZonasDomicilioInput,
)

server = MCPServer(
    name="sabor-de-casa",
    instructions=(
        "Servidor MCP para el restaurante colombiano Sabor de Casa en Bogotá. "
        "Proporciona herramientas para consultar menú con precios y alérgenos, "
        "horarios de atención, creación y validación de reservas, estado de pedidos "
        "y cobertura de domicilios."
    ),
    version="1.0.0",
)


def _strip_accents(text: str) -> str:
    """Normalize text removing accents for robust matching."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


@server.tool(
    name="consultar_menu",
    description="Consulta los platos del menú, precios en COP, ingredientes y alérgenos.",
)
def consultar_menu(categoria: str | None = None, plato: str | None = None) -> dict:
    """Consulta los platos del menú de Sabor de Casa."""
    try:
        ConsultarMenuInput(categoria=categoria, plato=plato)
    except ValidationError as err:
        return {"error": "validacion_fallida", "mensaje": str(err)}

    menu_items = parse_menu()

    if plato:
        norm_query = _strip_accents(plato.strip())
        matches = [item.to_dict() for item in menu_items if norm_query in _strip_accents(item.name)]
        if not matches:
            return {
                "encontrado": False,
                "mensaje": f"El plato '{plato}' no se encuentra en el menú de Sabor de Casa.",
                "platos_disponibles": [item.name for item in menu_items],
            }
        return {"encontrado": True, "total": len(matches), "platos": matches}

    if categoria:
        norm_cat = _strip_accents(categoria.strip())
        cat_map = {
            "plato fuerte": "plato_fuerte",
            "platos fuertes": "plato_fuerte",
            "fuerte": "plato_fuerte",
            "fuertes": "plato_fuerte",
            "plato_fuerte": "plato_fuerte",
            "entrada": "entrada",
            "entradas": "entrada",
            "postre": "postre",
            "postres": "postre",
            "bebida": "bebida",
            "bebidas": "bebida",
        }
        resolved_cat = cat_map.get(norm_cat, norm_cat)
        filtered = [item.to_dict() for item in menu_items if item.category == resolved_cat]
        return {
            "categoria": categoria,
            "total": len(filtered),
            "platos": filtered,
        }

    return {
        "total": len(menu_items),
        "platos": [item.to_dict() for item in menu_items],
    }


@server.tool(
    name="consultar_horario",
    description="Consulta los horarios de atención y días de operación del restaurante.",
)
def consultar_horario(dia: str | None = None) -> dict:
    """Consulta el horario de atención para un día específico o general."""
    try:
        ConsultarHorarioInput(dia=dia)
    except ValidationError as err:
        return {"error": "validacion_fallida", "mensaje": str(err)}

    if not dia:
        return {
            "horario_general": (
                "Martes a domingo: 12:00 m. a 9:00 p.m. (último ingreso 8:30 p.m.)"
            ),
            "lunes": "Cerrado todo el día (descanso del equipo de cocina)",
            "festivos": "Abierto de 12:00 m. a 9:00 p.m. (horario de domingo)",
            "atencion_whatsapp": (
                "Asistente virtual 24 horas; atención humana en horario de servicio."
            ),
        }

    norm_dia = _strip_accents(dia.strip())
    if "lunes" in norm_dia:
        return {
            "dia": "lunes",
            "abierto": False,
            "mensaje": (
                "Los lunes el restaurante está cerrado todo el día por descanso del "
                "equipo de cocina."
            ),
        }

    dias_abiertos = ["martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
    for d in dias_abiertos:
        if d in norm_dia:
            return {
                "dia": d.capitalize(),
                "abierto": True,
                "apertura": "12:00 m.",
                "cierre": "9:00 p.m.",
                "ultimo_ingreso": "8:30 p.m.",
                "mensaje": (
                    f"El {d.capitalize()} atendemos de 12:00 m. a 9:00 p.m. "
                    "(último ingreso de mesa a las 8:30 p.m.)."
                ),
            }

    if "festivo" in norm_dia:
        return {
            "dia": "Festivo",
            "abierto": True,
            "apertura": "12:00 m.",
            "cierre": "9:00 p.m.",
            "ultimo_ingreso": "8:30 p.m.",
            "mensaje": (
                "Los días festivos abrimos con el horario habitual de domingo "
                "(12:00 m. a 9:00 p.m.)."
            ),
        }

    return {
        "dia": dia,
        "mensaje": (
            "No se reconoció el día solicitado. Nuestro horario habitual es martes a domingo "
            "de 12:00 m. a 9:00 p.m. (lunes cerrado)."
        ),
    }


@server.tool(
    name="crear_reserva",
    description="Crea una reserva de mesa validando fecha, hora, personas (máx 12) y cupo.",
)
def crear_reserva(
    nombre: str,
    telefono: str,
    fecha: str,
    hora: str,
    personas: int,
) -> dict:
    """Crea una reserva en el restaurante Sabor de Casa tras validar políticas."""
    try:
        validated = CrearReservaInput(
            nombre=nombre,
            telefono=telefono,
            fecha=fecha,
            hora=hora,
            personas=personas,
        )
    except ValidationError as err:
        error_msgs = "; ".join(e["msg"] for e in err.errors())
        # Clean standard Pydantic prefixes if present
        clean_msgs = error_msgs.replace("Value error, ", "")
        return {
            "error": "politica_incumplida",
            "mensaje": clean_msgs,
        }

    result = crear_reserva_db(
        nombre=validated.nombre,
        telefono=validated.telefono,
        fecha=validated.fecha,
        hora=validated.hora,
        personas=validated.personas,
    )
    return result


@server.tool(
    name="estado_pedido",
    description="Consulta el estado actual de un pedido a domicilio por su número identificador.",
)
def estado_pedido(id_pedido: int) -> dict:
    """Consulta el estado de un pedido en la base de datos."""
    try:
        EstadoPedidoInput(id_pedido=id_pedido)
    except ValidationError as err:
        return {"error": "validacion_fallida", "mensaje": str(err)}

    pedido = obtener_pedido_db(id_pedido)
    if not pedido:
        return {
            "encontrado": False,
            "mensaje": (
                f"No se encontró ningún pedido con el número #{id_pedido}. "
                "Por favor verifica el número ingresado."
            ),
        }

    return {
        "encontrado": True,
        "id_pedido": pedido["id"],
        "estado": pedido["estado"],
        "total_cop": pedido["total_cop"],
        "total_formato": f"${pedido['total_cop']:,}".replace(",", "."),
        "direccion": pedido["direccion"],
        "zona": pedido["zona"],
        "items": pedido["items"],
        "fecha": pedido["created_at"],
    }


@server.tool(
    name="zonas_domicilio",
    description="Consulta la cobertura de domicilios en Bogotá, costos por zona y tiempos.",
)
def zonas_domicilio(zona: str | None = None) -> dict:
    """Consulta las zonas de domicilio de Sabor de Casa."""
    try:
        ZonasDomicilioInput(zona=zona)
    except ValidationError as err:
        return {"error": "validacion_fallida", "mensaje": str(err)}

    all_zones = parse_delivery_zones()
    pedido_minimo = "$25.000"

    if not zona:
        return {
            "zonas_cubiertas": [z.to_dict() for z in all_zones],
            "pedido_minimo": pedido_minimo,
            "politica": (
                "Solo cubrimos zonas autorizadas en Bogotá. "
                "Pedido mínimo $25.000 antes del costo de domicilio."
            ),
        }

    norm_query = _strip_accents(zona.strip())
    matched_zone = None
    for z in all_zones:
        if _strip_accents(z.zone) in norm_query or norm_query in _strip_accents(z.zone):
            matched_zone = z
            break

    if matched_zone:
        return {
            "cobertura": True,
            "zona": matched_zone.zone,
            "costo": matched_zone.cost_text,
            "costo_cop": matched_zone.cost_cop,
            "tiempo_estimado": matched_zone.estimated_time,
            "pedido_minimo": pedido_minimo,
            "mensaje": (
                f"La zona {matched_zone.zone} cuenta con cobertura de domicilios. "
                f"Costo de envío: {matched_zone.cost_text}, "
                f"tiempo estimado: {matched_zone.estimated_time}. "
                f"Pedido mínimo: {pedido_minimo}."
            ),
        }

    zonas_nombradas = ", ".join(z.zone for z in all_zones)
    return {
        "cobertura": False,
        "zona": zona,
        "mensaje": (
            f"La zona '{zona}' está fuera de nuestra cobertura de domicilios "
            f"(no cuenta con cobertura). Nuestra cobertura se limita a: {zonas_nombradas}. "
            "Ofrecemos la opción de recoger el pedido en nuestro local (Calle 63 #11-25) "
            "o entregarlo en una dirección dentro de nuestras zonas habilitadas."
        ),
        "zonas_disponibles": [z.zone for z in all_zones],
    }


@server.resource(
    uri="politicas://sabor-de-casa/politicas",
    name="politicas_sabor_de_casa",
    description="Políticas completas de Sabor de Casa (horarios, reservas, domicilios, pagos).",
    mime_type="text/markdown",
)
def politicas() -> str:
    """Devuelve el compendio completo de políticas del restaurante."""
    return load_all_policies()


def main() -> None:
    """CLI entrypoint to run the MCP server with stdio or HTTP transport."""
    parser = argparse.ArgumentParser(description="Servidor MCP Sabor de Casa")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http", "sse"],
        default="stdio",
        help="Transporte MCP a utilizar (por defecto stdio)",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host para servidor HTTP/SSE")
    parser.add_argument("--port", type=int, default=8000, help="Puerto para servidor HTTP/SSE")
    args = parser.parse_args()

    init_db()

    if args.transport == "stdio":
        server.run(transport="stdio")
    elif args.transport in ("streamable-http", "sse"):
        server.run(transport=args.transport, host=args.host, port=args.port)
    else:
        sys.exit(f"Transporte desconocido: {args.transport}")


if __name__ == "__main__":
    main()
