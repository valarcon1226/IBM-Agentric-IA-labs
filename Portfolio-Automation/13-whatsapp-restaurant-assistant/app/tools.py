"""Server-side business logic for the agent's tools (DECISIONES-13 W6/W8).

Every function takes `wa_id` as its first argument — the server always injects it from the
authenticated sender (webhook signature / dev-chat bearer token), the LLM never supplies it, so a
customer can only ever act on their own orders and reservations. Each function returns a small
JSON-serializable dict: either the result, or `{"error": <code>, "message": <text>}` with a code
the agent can explain to the customer and a `message` it can also use verbatim.

Prices, zone coverage and reservation rules mirror `knowledge/menu.md`,
`knowledge/zonas_domicilio.md` and `knowledge/reservas_politicas.md` — keep them in sync if those
files change.

`dispatch_tool` catches any unexpected exception (DB error, malformed LLM arguments) and turns it
into a generic `internal_error` instead of letting it escape and break the conversation (batch C).
"""

import datetime as dt
import logging
from dataclasses import dataclass
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import text

from app import sheets
from app.database import get_engine
from app.security import mask_wa_id
from app.text_utils import normalize_key

logger = logging.getLogger(__name__)

BOGOTA_TZ = ZoneInfo("America/Bogota")

# knowledge/zonas_domicilio.md
ZONE_DELIVERY_FEES_COP = {
    "chapinero": 5000,
    "teusaquillo": 6000,
    "usaquen": 7000,
    "suba": 9000,
}
MIN_ORDER_COP = 25000
PAYMENT_METHODS = {"contraentrega", "link_pago"}
MAX_ITEM_QUANTITY = 50
MAX_ORDER_QUANTITY = 100

# knowledge/reservas_politicas.md and knowledge/horarios.md
CLOSED_WEEKDAY = 0  # Monday (date.weekday(): Monday=0)
OPENING_TIME = dt.time(12, 0)
LAST_SLOT_TIME = dt.time(20, 30)
SLOT_MINUTES = 30
MAX_PARTY_SIZE = 12
MAX_CAPACITY_PER_SLOT = 40
MAX_FUTURE_DAYS = 60


class ToolError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message

    def to_dict(self) -> dict[str, str]:
        return {"error": self.code, "message": self.message}


def today_bogota() -> dt.date:
    return dt.datetime.now(BOGOTA_TZ).date()


def _parse_date(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise ToolError(
            "invalid_date", f"'{value}' no es una fecha válida (usa AAAA-MM-DD)."
        ) from exc


def _parse_time(value: str) -> dt.time:
    try:
        return dt.time.fromisoformat(value)
    except ValueError as exc:
        raise ToolError("invalid_time", f"'{value}' no es una hora válida (usa HH:MM).") from exc


def _validate_reservation_slot(
    date_str: str, time_str: str, party_size: int
) -> tuple[dt.date, dt.time]:
    reservation_date = _parse_date(date_str)
    reservation_time = _parse_time(time_str)

    today = today_bogota()
    if reservation_date < today:
        raise ToolError("date_in_past", "No se pueden hacer reservas para una fecha pasada.")
    if reservation_date > today + dt.timedelta(days=MAX_FUTURE_DAYS):
        raise ToolError(
            "date_too_far",
            f"Solo se puede reservar hasta {MAX_FUTURE_DAYS} días en el futuro.",
        )
    if reservation_date.weekday() == CLOSED_WEEKDAY:
        raise ToolError("closed_that_day", "Los lunes el restaurante está cerrado.")
    if reservation_time.minute not in (0, SLOT_MINUTES) or reservation_time.second != 0:
        raise ToolError(
            "invalid_time_slot", "Las reservas son en franjas de 30 minutos (ej. 19:00, 19:30)."
        )
    if not (OPENING_TIME <= reservation_time <= LAST_SLOT_TIME):
        raise ToolError(
            "outside_hours",
            f"El horario de reservas es de {OPENING_TIME:%H:%M} a {LAST_SLOT_TIME:%H:%M}.",
        )
    if party_size < 1:
        raise ToolError("invalid_party_size", "El número de personas debe ser al menos 1.")
    if party_size > MAX_PARTY_SIZE:
        raise ToolError(
            "party_too_large",
            f"Para más de {MAX_PARTY_SIZE} personas gestionamos un evento, no una reserva de "
            "mesa: usa register_event_lead.",
        )
    return reservation_date, reservation_time


_SUM_PARTY_SIZE_AT_SLOT_SQL = text(
    "SELECT COALESCE(SUM(party_size), 0) FROM reservations "
    "WHERE reservation_date = :reservation_date AND reservation_time = :reservation_time "
    "AND status = 'confirmed' AND id != :exclude_id"
)


async def _booked_party_size(
    reservation_date: dt.date, reservation_time: dt.time, exclude_id: int
) -> int:
    async with get_engine().connect() as connection:
        result = await connection.execute(
            _SUM_PARTY_SIZE_AT_SLOT_SQL,
            {
                "reservation_date": reservation_date,
                "reservation_time": reservation_time,
                "exclude_id": exclude_id,
            },
        )
        return int(result.scalar_one())


@dataclass(frozen=True)
class _MenuRow:
    id: int
    name: str
    category: str
    allergens: str | None
    price_cop: int
    available: bool


_SELECT_MENU_SQL = text(
    "SELECT id, name, category, allergens, price_cop, available FROM menu ORDER BY category, name"
)


async def _load_menu() -> list[_MenuRow]:
    async with get_engine().connect() as connection:
        result = await connection.execute(_SELECT_MENU_SQL)
        return [_MenuRow(*row) for row in result.all()]


async def get_menu(wa_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
    dishes = await _load_menu()
    return {
        "dishes": [
            {
                "dish_id": dish.id,
                "name": dish.name,
                "category": dish.category,
                "price_cop": dish.price_cop,
                "available": dish.available,
                "allergens": dish.allergens,
            }
            for dish in dishes
        ]
    }


_INSERT_ORDER_SQL = text(
    "INSERT INTO orders (wa_id, total_cop, address, zone, payment_method) "
    "VALUES (:wa_id, :total_cop, :address, :zone, :payment_method) RETURNING id"
)
_INSERT_ORDER_ITEM_SQL = text(
    "INSERT INTO order_items (order_id, dish_id, quantity, unit_price_cop, notes) "
    "VALUES (:order_id, :dish_id, :quantity, :unit_price_cop, :notes)"
)


async def create_order(wa_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
    items = arguments.get("items") or []
    address = (arguments.get("address") or "").strip()
    zone_raw = (arguments.get("zone") or "").strip()
    payment_method = (arguments.get("payment_method") or "").strip()

    if not items:
        raise ToolError("empty_order", "El pedido debe tener al menos un plato.")
    if not address:
        raise ToolError("missing_address", "Falta la dirección de entrega.")
    if payment_method not in PAYMENT_METHODS:
        raise ToolError(
            "invalid_payment_method",
            f"El medio de pago debe ser uno de: {', '.join(sorted(PAYMENT_METHODS))}.",
        )

    zone_key = normalize_key(zone_raw)
    if zone_key not in ZONE_DELIVERY_FEES_COP:
        raise ToolError(
            "zone_not_covered",
            f"No cubrimos domicilios en '{zone_raw}'. Zonas disponibles: "
            f"{', '.join(sorted(ZONE_DELIVERY_FEES_COP))}.",
        )
    delivery_fee = ZONE_DELIVERY_FEES_COP[zone_key]

    menu_by_id = {dish.id: dish for dish in await _load_menu()}
    resolved_items: list[dict[str, Any]] = []
    subtotal = 0
    for raw_item in items:
        dish_id = raw_item.get("dish_id")
        quantity = raw_item.get("qty", 1)
        dish = menu_by_id.get(dish_id)
        if dish is None:
            raise ToolError("dish_not_found", f"El plato con id {dish_id} no existe.")
        if not dish.available:
            raise ToolError("dish_unavailable", f"'{dish.name}' no está disponible ahora.")
        if not isinstance(quantity, int) or quantity < 1:
            raise ToolError(
                "invalid_quantity", f"La cantidad de '{dish.name}' debe ser al menos 1."
            )
        if quantity > MAX_ITEM_QUANTITY:
            raise ToolError(
                "quantity_too_high",
                f"La cantidad máxima por plato es {MAX_ITEM_QUANTITY} ('{dish.name}').",
            )
        line_total = dish.price_cop * quantity
        subtotal += line_total
        resolved_items.append(
            {
                "dish_id": dish.id,
                "name": dish.name,
                "quantity": quantity,
                "unit_price_cop": dish.price_cop,
                "notes": raw_item.get("notes"),
            }
        )

    total_quantity = sum(item["quantity"] for item in resolved_items)
    if total_quantity > MAX_ORDER_QUANTITY:
        raise ToolError(
            "order_too_large",
            f"El pedido no puede superar {MAX_ORDER_QUANTITY} unidades en total "
            f"(este pedido suma {total_quantity}).",
        )

    if subtotal < MIN_ORDER_COP:
        raise ToolError(
            "below_minimum",
            f"El pedido mínimo para domicilio es ${MIN_ORDER_COP:,} COP (antes de domicilio); "
            f"este pedido suma ${subtotal:,} COP.".replace(",", "."),
        )

    total_cop = subtotal + delivery_fee
    async with get_engine().begin() as connection:
        result = await connection.execute(
            _INSERT_ORDER_SQL,
            {
                "wa_id": wa_id,
                "total_cop": total_cop,
                "address": address,
                "zone": zone_key,
                "payment_method": payment_method,
            },
        )
        order_id: int = result.scalar_one()
        for item in resolved_items:
            await connection.execute(
                _INSERT_ORDER_ITEM_SQL,
                {
                    "order_id": order_id,
                    "dish_id": item["dish_id"],
                    "quantity": item["quantity"],
                    "unit_price_cop": item["unit_price_cop"],
                    "notes": item["notes"],
                },
            )

    result_data = {
        "order_id": order_id,
        "items": resolved_items,
        "subtotal_cop": subtotal,
        "delivery_fee_cop": delivery_fee,
        "total_cop": total_cop,
        "status": "pending",
    }
    await sheets.append_order(result_data, wa_id)
    return result_data


_SELECT_ORDER_SQL = text(
    "SELECT id, status, total_cop, address, zone, payment_method, created_at FROM orders "
    "WHERE id = :order_id AND wa_id = :wa_id"
)
_SELECT_ORDER_ITEMS_SQL = text(
    "SELECT m.name, oi.quantity, oi.unit_price_cop, oi.notes FROM order_items oi "
    "JOIN menu m ON m.id = oi.dish_id WHERE oi.order_id = :order_id"
)


async def get_order_status(wa_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
    order_id = arguments.get("order_id")
    if not isinstance(order_id, int):
        raise ToolError("invalid_order_id", "Debes indicar el número del pedido.")
    async with get_engine().connect() as connection:
        order_row = (
            await connection.execute(_SELECT_ORDER_SQL, {"order_id": order_id, "wa_id": wa_id})
        ).first()
        if order_row is None:
            # Same error for "doesn't exist" and "belongs to someone else": never confirm or deny
            # another customer's order id (DECISIONES-13 W6 "solo pedidos propios").
            raise ToolError("order_not_found", "No encontré un pedido tuyo con ese número.")
        items_result = await connection.execute(_SELECT_ORDER_ITEMS_SQL, {"order_id": order_id})
        items = [
            {"name": name, "quantity": quantity, "unit_price_cop": unit_price_cop, "notes": notes}
            for name, quantity, unit_price_cop, notes in items_result.all()
        ]
    return {
        "order_id": order_row.id,
        "status": order_row.status,
        "total_cop": order_row.total_cop,
        "address": order_row.address,
        "zone": order_row.zone,
        "payment_method": order_row.payment_method,
        "items": items,
    }


async def check_availability(wa_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
    date_str = arguments.get("date", "")
    time_str = arguments.get("time", "")
    party_size = arguments.get("party_size", 0)
    reservation_date, reservation_time = _validate_reservation_slot(date_str, time_str, party_size)

    used = await _booked_party_size(reservation_date, reservation_time, exclude_id=0)
    available = used + party_size <= MAX_CAPACITY_PER_SLOT
    return {
        "available": available,
        "capacity": MAX_CAPACITY_PER_SLOT,
        "already_booked": used,
    }


_INSERT_RESERVATION_SQL = text(
    "INSERT INTO reservations (wa_id, reservation_date, reservation_time, party_size) "
    "VALUES (:wa_id, :reservation_date, :reservation_time, :party_size) RETURNING id"
)


async def create_reservation(wa_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
    date_str = arguments.get("date", "")
    time_str = arguments.get("time", "")
    party_size = arguments.get("party_size", 0)
    reservation_date, reservation_time = _validate_reservation_slot(date_str, time_str, party_size)

    used = await _booked_party_size(reservation_date, reservation_time, exclude_id=0)
    if used + party_size > MAX_CAPACITY_PER_SLOT:
        raise ToolError("slot_full", "Esa franja ya está llena, por favor elige otra hora.")

    async with get_engine().begin() as connection:
        result = await connection.execute(
            _INSERT_RESERVATION_SQL,
            {
                "wa_id": wa_id,
                "reservation_date": reservation_date,
                "reservation_time": reservation_time,
                "party_size": party_size,
            },
        )
        reservation_id: int = result.scalar_one()

    result_data = {
        "reservation_id": reservation_id,
        "date": reservation_date.isoformat(),
        "time": reservation_time.isoformat(timespec="minutes"),
        "party_size": party_size,
        "status": "confirmed",
    }
    await sheets.append_reservation(result_data, wa_id)
    return result_data


_SELECT_RESERVATION_SQL = text(
    "SELECT id, reservation_date, reservation_time, party_size, status FROM reservations "
    "WHERE id = :reservation_id AND wa_id = :wa_id"
)
_UPDATE_RESERVATION_SQL = text(
    "UPDATE reservations SET reservation_date = :reservation_date, "
    "reservation_time = :reservation_time, party_size = :party_size WHERE id = :reservation_id"
)
_CANCEL_RESERVATION_SQL = text(
    "UPDATE reservations SET status = 'cancelled' WHERE id = :reservation_id"
)


async def _own_active_reservation(wa_id: str, reservation_id: int):
    async with get_engine().connect() as connection:
        row = (
            await connection.execute(
                _SELECT_RESERVATION_SQL, {"reservation_id": reservation_id, "wa_id": wa_id}
            )
        ).first()
    if row is None or row.status != "confirmed":
        # Same error whether the id doesn't exist, belongs to another customer, or is already
        # cancelled: never confirm the existence of someone else's reservation.
        raise ToolError(
            "reservation_not_found", "No encontré una reserva activa tuya con ese número."
        )
    return row


async def update_reservation(wa_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
    reservation_id = arguments.get("reservation_id")
    if not isinstance(reservation_id, int):
        raise ToolError("invalid_reservation_id", "Debes indicar el número de la reserva.")
    existing = await _own_active_reservation(wa_id, reservation_id)

    date_str = arguments.get("date") or existing.reservation_date.isoformat()
    time_str = arguments.get("time") or existing.reservation_time.isoformat(timespec="minutes")
    party_size = arguments.get("party_size", existing.party_size)

    reservation_date, reservation_time = _validate_reservation_slot(date_str, time_str, party_size)

    used = await _booked_party_size(reservation_date, reservation_time, exclude_id=reservation_id)
    if used + party_size > MAX_CAPACITY_PER_SLOT:
        raise ToolError("slot_full", "Esa franja ya está llena, por favor elige otra hora.")

    async with get_engine().begin() as connection:
        await connection.execute(
            _UPDATE_RESERVATION_SQL,
            {
                "reservation_id": reservation_id,
                "reservation_date": reservation_date,
                "reservation_time": reservation_time,
                "party_size": party_size,
            },
        )

    return {
        "reservation_id": reservation_id,
        "date": reservation_date.isoformat(),
        "time": reservation_time.isoformat(timespec="minutes"),
        "party_size": party_size,
        "status": "confirmed",
    }


async def cancel_reservation(wa_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
    reservation_id = arguments.get("reservation_id")
    if not isinstance(reservation_id, int):
        raise ToolError("invalid_reservation_id", "Debes indicar el número de la reserva.")
    await _own_active_reservation(wa_id, reservation_id)
    async with get_engine().begin() as connection:
        await connection.execute(_CANCEL_RESERVATION_SQL, {"reservation_id": reservation_id})
    return {"reservation_id": reservation_id, "status": "cancelled"}


_INSERT_EVENT_LEAD_SQL = text(
    "INSERT INTO event_leads (wa_id, event_type, event_date, guests, budget_cop, contact_name) "
    "VALUES (:wa_id, :event_type, :event_date, :guests, :budget_cop, :contact_name) RETURNING id"
)


async def register_event_lead(wa_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
    contact_name = (arguments.get("contact_name") or "").strip()
    if not contact_name:
        raise ToolError("missing_contact_name", "Falta el nombre de contacto para el evento.")

    event_date_str = arguments.get("date")
    event_date = _parse_date(event_date_str) if event_date_str else None

    guests = arguments.get("guests")
    if guests is not None and (not isinstance(guests, int) or guests < 1):
        raise ToolError("invalid_guests", "El número de invitados debe ser mayor a 0.")

    budget = arguments.get("budget")
    if budget is not None and (not isinstance(budget, int) or budget < 0):
        raise ToolError("invalid_budget", "El presupuesto debe ser un número positivo.")

    async with get_engine().begin() as connection:
        result = await connection.execute(
            _INSERT_EVENT_LEAD_SQL,
            {
                "wa_id": wa_id,
                "event_type": arguments.get("event_type"),
                "event_date": event_date,
                "guests": guests,
                "budget_cop": budget,
                "contact_name": contact_name,
            },
        )
        lead_id: int = result.scalar_one()

    result_data = {"lead_id": lead_id, "status": "new"}
    await sheets.append_event_lead(result_data, wa_id, arguments)
    return result_data


_INSERT_HANDOVER_SQL = text(
    "INSERT INTO handovers (wa_id, reason, expires_at) "
    "VALUES (:wa_id, :reason, :expires_at) RETURNING id"
)
_SELECT_ACTIVE_HANDOVER_SQL = text(
    "SELECT 1 FROM handovers WHERE wa_id = :wa_id AND active = TRUE AND expires_at > :now LIMIT 1"
)
_DEACTIVATE_HANDOVER_SQL = text(
    "UPDATE handovers SET active = FALSE WHERE wa_id = :wa_id AND active = TRUE"
)
_SELECT_LAST_CUSTOMER_MESSAGE_SQL = text(
    "SELECT content FROM messages WHERE wa_id = :wa_id AND role = 'customer' "
    "ORDER BY created_at DESC LIMIT 1"
)
HANDOVER_DURATION_HOURS = 12


async def _last_customer_message(wa_id: str) -> str | None:
    async with get_engine().connect() as connection:
        result = await connection.execute(_SELECT_LAST_CUSTOMER_MESSAGE_SQL, {"wa_id": wa_id})
        row = result.first()
    return row[0] if row else None


async def handover_to_human(wa_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
    reason = (arguments.get("reason") or "").strip() or "Solicitud del cliente."
    expires_at = dt.datetime.now(BOGOTA_TZ) + dt.timedelta(hours=HANDOVER_DURATION_HOURS)
    async with get_engine().begin() as connection:
        result = await connection.execute(
            _INSERT_HANDOVER_SQL,
            {"wa_id": wa_id, "reason": reason, "expires_at": expires_at.replace(tzinfo=None)},
        )
        handover_id: int = result.scalar_one()

    # A staff-notification failure must never break the conversation: `notify_staff` already
    # swallows and logs its own errors (see app.staff), so this call is never wrapped here.
    # Imported lazily to avoid a module-load-time cycle: app.staff imports app.whatsapp, which
    # (like app.tools) is fine on its own, but keeping the import local matches app.sheets' usage
    # in this same function and keeps module-level import order simple.
    from app.staff import notify_staff

    summary = (await _last_customer_message(wa_id) or reason)[:200]
    await notify_staff(reason, wa_id, summary)

    return {"handover_id": handover_id, "ok": True}


async def is_handover_active(wa_id: str) -> bool:
    """True while the bot must stay silent for this customer (DECISIONES-13 W7)."""
    now = dt.datetime.now(BOGOTA_TZ).replace(tzinfo=None)
    async with get_engine().connect() as connection:
        result = await connection.execute(_SELECT_ACTIVE_HANDOVER_SQL, {"wa_id": wa_id, "now": now})
        return result.first() is not None


async def deactivate_handover(wa_id: str) -> None:
    """Give control back to the bot for this customer (staff `/bot <wa_id>` command)."""
    async with get_engine().begin() as connection:
        await connection.execute(_DEACTIVATE_HANDOVER_SQL, {"wa_id": wa_id})


TOOL_HANDLERS = {
    "get_menu": get_menu,
    "create_order": create_order,
    "get_order_status": get_order_status,
    "check_availability": check_availability,
    "create_reservation": create_reservation,
    "update_reservation": update_reservation,
    "cancel_reservation": cancel_reservation,
    "register_event_lead": register_event_lead,
    "handover_to_human": handover_to_human,
}


INTERNAL_ERROR_MESSAGE = (
    "Tuvimos un problema interno procesando tu solicitud. Intenta de nuevo o pide hablar "
    "con una persona."
)


async def dispatch_tool(name: str, wa_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        return {"error": "unknown_tool", "message": f"La herramienta '{name}' no existe."}
    try:
        return await handler(wa_id, arguments)
    except ToolError as error:
        return error.to_dict()
    except Exception:
        # Any other exception (a DB error, malformed LLM arguments such as a string where a list
        # or int was expected, a missing key) must never break the conversation: log it without
        # message bodies or full phone numbers, and let the agent apologize generically.
        logger.exception("Unexpected error running tool '%s' for wa_id=%s", name, mask_wa_id(wa_id))
        return {"error": "internal_error", "message": INTERNAL_ERROR_MESSAGE}
