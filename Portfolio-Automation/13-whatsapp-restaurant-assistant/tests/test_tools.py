"""Unit tests for app.tools (DECISIONES-13 W6/W10): every business rule, success and failure.

`app.database.get_engine` is replaced with an in-memory fake that understands exactly the SQL
`app.tools` issues (matched by substring, since the module always uses its own `text(...)`
constants) — no real Postgres involved, that is covered by the integration/E2E suite.
"""

from collections import namedtuple
from itertools import count

import pytest

from app import tools

MenuRow = namedtuple("MenuRow", ["id", "name", "category", "allergens", "price_cop", "available"])
OrderRow = namedtuple(
    "OrderRow",
    ["id", "wa_id", "status", "total_cop", "address", "zone", "payment_method", "created_at"],
)
OrderItemRow = namedtuple("OrderItemRow", ["name", "quantity", "unit_price_cop", "notes"])
ReservationRow = namedtuple(
    "ReservationRow",
    ["id", "wa_id", "reservation_date", "reservation_time", "party_size", "status"],
)

SEED_MENU = [
    MenuRow(1, "Bandeja Paisa", "plato_fuerte", "gluten (chorizo)", 34000, True),
    MenuRow(2, "Ajiaco Santafereño", "plato_fuerte", "lacteos", 29000, True),
    MenuRow(3, "Limonada de Coco", "bebida", "lacteos", 9000, True),
    MenuRow(4, "Lechona Tolimense", "plato_fuerte", "ninguno", 25000, False),  # agotado
]


class FakeResult:
    def __init__(self, rows=None, scalar=None):
        self._rows = rows or []
        self._scalar = scalar

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return self._rows

    def scalar_one(self):
        return self._scalar


class FakeConnection:
    def __init__(self, db: "FakeDB"):
        self.db = db

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def execute(self, statement, params=None):
        return self.db.execute(str(statement), params or {})


class FakeDB:
    def __init__(self, menu=SEED_MENU):
        self.menu = list(menu)
        self.orders: dict[int, OrderRow] = {}
        # (order_id, dish_id, qty, price, notes)
        self.order_items: list[tuple[int, int, int, int, str | None]] = []
        self.reservations: dict[int, ReservationRow] = {}
        self.event_leads: list[dict] = []
        self.handovers: list[dict] = []
        self._ids = count(1)

    def connect(self):
        return FakeConnection(self)

    def begin(self):
        return FakeConnection(self)

    def execute(self, sql: str, params: dict):
        if "FROM menu ORDER BY category" in sql:
            return FakeResult(rows=[tuple(row) for row in self.menu])

        if sql.startswith("INSERT INTO orders"):
            order_id = next(self._ids)
            self.orders[order_id] = OrderRow(
                order_id,
                params["wa_id"],
                "pending",
                params["total_cop"],
                params["address"],
                params["zone"],
                params["payment_method"],
                None,
            )
            return FakeResult(scalar=order_id)

        if sql.startswith("INSERT INTO order_items"):
            self.order_items.append(
                (
                    params["order_id"],
                    params["dish_id"],
                    params["quantity"],
                    params["unit_price_cop"],
                    params["notes"],
                )
            )
            return FakeResult()

        if "FROM orders" in sql and "WHERE id = :order_id AND wa_id = :wa_id" in sql:
            order = self.orders.get(params["order_id"])
            if order is None or order.wa_id != params["wa_id"]:
                return FakeResult(rows=[])
            return FakeResult(rows=[order])

        if "FROM order_items oi" in sql:
            menu_by_id = {row.id: row for row in self.menu}
            items = [
                OrderItemRow(menu_by_id[dish_id].name, qty, price, notes)
                for (order_id, dish_id, qty, price, notes) in self.order_items
                if order_id == params["order_id"]
            ]
            return FakeResult(rows=items)

        if "SUM(party_size)" in sql:
            total = sum(
                r.party_size
                for r in self.reservations.values()
                if r.reservation_date == params["reservation_date"]
                and r.reservation_time == params["reservation_time"]
                and r.status == "confirmed"
                and r.id != params["exclude_id"]
            )
            return FakeResult(scalar=total)

        if sql.startswith("INSERT INTO reservations"):
            reservation_id = next(self._ids)
            self.reservations[reservation_id] = ReservationRow(
                reservation_id,
                params["wa_id"],
                params["reservation_date"],
                params["reservation_time"],
                params["party_size"],
                "confirmed",
            )
            return FakeResult(scalar=reservation_id)

        if "FROM reservations WHERE id = :reservation_id AND wa_id = :wa_id" in sql:
            reservation = self.reservations.get(params["reservation_id"])
            if reservation is None or reservation.wa_id != params["wa_id"]:
                return FakeResult(rows=[])
            return FakeResult(rows=[reservation])

        if sql.startswith("UPDATE reservations SET reservation_date"):
            reservation_id = params["reservation_id"]
            existing = self.reservations[reservation_id]
            self.reservations[reservation_id] = existing._replace(
                reservation_date=params["reservation_date"],
                reservation_time=params["reservation_time"],
                party_size=params["party_size"],
            )
            return FakeResult()

        if sql.startswith("UPDATE reservations SET status = 'cancelled'"):
            reservation_id = params["reservation_id"]
            self.reservations[reservation_id] = self.reservations[reservation_id]._replace(
                status="cancelled"
            )
            return FakeResult()

        if sql.startswith("INSERT INTO event_leads"):
            lead_id = next(self._ids)
            self.event_leads.append({"id": lead_id, **params})
            return FakeResult(scalar=lead_id)

        if sql.startswith("INSERT INTO handovers"):
            handover_id = next(self._ids)
            self.handovers.append({"id": handover_id, **params})
            return FakeResult(scalar=handover_id)

        if sql.startswith("SELECT content FROM messages"):
            return FakeResult(rows=[])  # no message history in this fake: falls back to `reason`

        raise AssertionError(f"FakeDB got an unrecognized query: {sql}")


@pytest.fixture
def db(monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr(tools, "get_engine", lambda: fake_db)
    return fake_db


WA_ID = "573001234567"
OTHER_WA_ID = "573009998888"


# --- get_menu -----------------------------------------------------------------------------


async def test_get_menu_returns_all_dishes_with_availability(db):
    result = await tools.dispatch_tool("get_menu", WA_ID, {})
    assert len(result["dishes"]) == len(SEED_MENU)
    unavailable = [d for d in result["dishes"] if not d["available"]]
    assert unavailable[0]["name"] == "Lechona Tolimense"


# --- create_order ---------------------------------------------------------------------------


def _order_args(**overrides):
    args = {
        "items": [{"dish_id": 1, "qty": 1}],
        "address": "Calle 10 #5-20",
        "zone": "Chapinero",
        "payment_method": "contraentrega",
    }
    args.update(overrides)
    return args


async def test_create_order_computes_server_side_total(db):
    result = await tools.dispatch_tool(
        "create_order",
        WA_ID,
        _order_args(items=[{"dish_id": 1, "qty": 1}, {"dish_id": 3, "qty": 2}]),
    )
    # 34000*1 + 9000*2 = 52000 subtotal, Chapinero fee 5000 -> 57000
    assert result["subtotal_cop"] == 52000
    assert result["delivery_fee_cop"] == 5000
    assert result["total_cop"] == 57000
    assert "order_id" in result


async def test_create_order_unknown_dish(db):
    result = await tools.dispatch_tool(
        "create_order", WA_ID, _order_args(items=[{"dish_id": 999, "qty": 1}])
    )
    assert result["error"] == "dish_not_found"


async def test_create_order_unavailable_dish(db):
    result = await tools.dispatch_tool(
        "create_order", WA_ID, _order_args(items=[{"dish_id": 4, "qty": 1}])
    )
    assert result["error"] == "dish_unavailable"


async def test_create_order_zone_not_covered(db):
    result = await tools.dispatch_tool("create_order", WA_ID, _order_args(zone="Kennedy"))
    assert result["error"] == "zone_not_covered"


async def test_create_order_below_minimum(db):
    result = await tools.dispatch_tool(
        "create_order", WA_ID, _order_args(items=[{"dish_id": 3, "qty": 1}])
    )
    assert result["error"] == "below_minimum"


async def test_create_order_invalid_payment_method(db):
    result = await tools.dispatch_tool("create_order", WA_ID, _order_args(payment_method="bitcoin"))
    assert result["error"] == "invalid_payment_method"


async def test_create_order_quantity_too_high_for_a_single_item(db):
    result = await tools.dispatch_tool(
        "create_order", WA_ID, _order_args(items=[{"dish_id": 1, "qty": 51}])
    )
    assert result["error"] == "quantity_too_high"


async def test_create_order_too_large_in_total(db):
    result = await tools.dispatch_tool(
        "create_order",
        WA_ID,
        _order_args(
            items=[
                {"dish_id": 1, "qty": 50},
                {"dish_id": 2, "qty": 50},
                {"dish_id": 3, "qty": 1},
            ]
        ),
    )
    assert result["error"] == "order_too_large"


async def test_dispatch_tool_turns_unexpected_exception_into_internal_error(db):
    # `items` as a string (not a list) is a malformed-LLM-argument case: iterating over it
    # yields characters instead of dicts, so `raw_item.get(...)` blows up with an AttributeError
    # deep inside `create_order` — `dispatch_tool` must catch it instead of letting it escape.
    result = await tools.dispatch_tool("create_order", WA_ID, _order_args(items="not-a-list"))
    assert result["error"] == "internal_error"
    assert "message" in result


# --- get_order_status -----------------------------------------------------------------------


async def test_get_order_status_own_order(db):
    created = await tools.dispatch_tool("create_order", WA_ID, _order_args())
    result = await tools.dispatch_tool("get_order_status", WA_ID, {"order_id": created["order_id"]})
    assert result["status"] == "pending"
    assert result["total_cop"] == created["total_cop"]


async def test_get_order_status_rejects_other_customers_order(db):
    created = await tools.dispatch_tool("create_order", WA_ID, _order_args())
    result = await tools.dispatch_tool(
        "get_order_status", OTHER_WA_ID, {"order_id": created["order_id"]}
    )
    assert result["error"] == "order_not_found"


async def test_get_order_status_unknown_order(db):
    result = await tools.dispatch_tool("get_order_status", WA_ID, {"order_id": 999})
    assert result["error"] == "order_not_found"


# --- check_availability / create_reservation -------------------------------------------------


def _future_tuesday() -> str:
    import datetime as dt

    today = tools.today_bogota()
    offset = (1 - today.weekday()) % 7 or 7  # next Tuesday, never today
    return (today + dt.timedelta(days=offset)).isoformat()


async def test_check_availability_open_slot(db):
    result = await tools.dispatch_tool(
        "check_availability", WA_ID, {"date": _future_tuesday(), "time": "19:00", "party_size": 4}
    )
    assert result["available"] is True


async def test_create_reservation_success(db):
    result = await tools.dispatch_tool(
        "create_reservation", WA_ID, {"date": _future_tuesday(), "time": "19:00", "party_size": 4}
    )
    assert result["status"] == "confirmed"
    assert "reservation_id" in result


async def test_create_reservation_closed_on_monday(db):
    import datetime as dt

    today = tools.today_bogota()
    offset = (0 - today.weekday()) % 7 or 7
    monday = (today + dt.timedelta(days=offset)).isoformat()
    result = await tools.dispatch_tool(
        "create_reservation", WA_ID, {"date": monday, "time": "19:00", "party_size": 2}
    )
    assert result["error"] == "closed_that_day"


async def test_create_reservation_outside_hours(db):
    result = await tools.dispatch_tool(
        "create_reservation", WA_ID, {"date": _future_tuesday(), "time": "10:00", "party_size": 2}
    )
    assert result["error"] == "outside_hours"


async def test_create_reservation_invalid_slot_not_on_half_hour(db):
    result = await tools.dispatch_tool(
        "create_reservation", WA_ID, {"date": _future_tuesday(), "time": "19:15", "party_size": 2}
    )
    assert result["error"] == "invalid_time_slot"


async def test_create_reservation_party_too_large_suggests_event(db):
    result = await tools.dispatch_tool(
        "create_reservation", WA_ID, {"date": _future_tuesday(), "time": "19:00", "party_size": 13}
    )
    assert result["error"] == "party_too_large"


async def test_create_reservation_date_in_past(db):
    result = await tools.dispatch_tool(
        "create_reservation", WA_ID, {"date": "2000-01-01", "time": "19:00", "party_size": 2}
    )
    assert result["error"] == "date_in_past"


async def test_create_reservation_too_far_in_future(db):
    import datetime as dt

    far = (tools.today_bogota() + dt.timedelta(days=120)).isoformat()
    result = await tools.dispatch_tool(
        "create_reservation", WA_ID, {"date": far, "time": "19:00", "party_size": 2}
    )
    assert result["error"] == "date_too_far"


async def test_create_reservation_capacity_full(db):
    date = _future_tuesday()
    await tools.dispatch_tool(
        "create_reservation", WA_ID, {"date": date, "time": "19:00", "party_size": 12}
    )
    await tools.dispatch_tool(
        "create_reservation", WA_ID, {"date": date, "time": "19:00", "party_size": 12}
    )
    await tools.dispatch_tool(
        "create_reservation", WA_ID, {"date": date, "time": "19:00", "party_size": 12}
    )
    result = await tools.dispatch_tool(
        "create_reservation", WA_ID, {"date": date, "time": "19:00", "party_size": 5}
    )
    assert result["error"] == "slot_full"


# --- update_reservation / cancel_reservation --------------------------------------------------


async def test_update_reservation_own(db):
    created = await tools.dispatch_tool(
        "create_reservation", WA_ID, {"date": _future_tuesday(), "time": "19:00", "party_size": 2}
    )
    result = await tools.dispatch_tool(
        "update_reservation",
        WA_ID,
        {"reservation_id": created["reservation_id"], "party_size": 6},
    )
    assert result["party_size"] == 6


async def test_update_reservation_rejects_other_customer(db):
    created = await tools.dispatch_tool(
        "create_reservation", WA_ID, {"date": _future_tuesday(), "time": "19:00", "party_size": 2}
    )
    result = await tools.dispatch_tool(
        "update_reservation",
        OTHER_WA_ID,
        {"reservation_id": created["reservation_id"], "party_size": 6},
    )
    assert result["error"] == "reservation_not_found"


async def test_cancel_reservation_own(db):
    created = await tools.dispatch_tool(
        "create_reservation", WA_ID, {"date": _future_tuesday(), "time": "19:00", "party_size": 2}
    )
    result = await tools.dispatch_tool(
        "cancel_reservation", WA_ID, {"reservation_id": created["reservation_id"]}
    )
    assert result["status"] == "cancelled"


async def test_cancel_reservation_rejects_other_customer(db):
    created = await tools.dispatch_tool(
        "create_reservation", WA_ID, {"date": _future_tuesday(), "time": "19:00", "party_size": 2}
    )
    result = await tools.dispatch_tool(
        "cancel_reservation", OTHER_WA_ID, {"reservation_id": created["reservation_id"]}
    )
    assert result["error"] == "reservation_not_found"


async def test_cancel_reservation_unknown(db):
    result = await tools.dispatch_tool("cancel_reservation", WA_ID, {"reservation_id": 999})
    assert result["error"] == "reservation_not_found"


# --- register_event_lead / handover_to_human --------------------------------------------------


async def test_register_event_lead_success(db):
    result = await tools.dispatch_tool(
        "register_event_lead",
        WA_ID,
        {"event_type": "matrimonio", "guests": 80, "budget": 5000000, "contact_name": "Juan"},
    )
    assert result["status"] == "new"
    assert "lead_id" in result


async def test_register_event_lead_missing_contact_name(db):
    result = await tools.dispatch_tool(
        "register_event_lead", WA_ID, {"event_type": "cumpleaños", "guests": 20}
    )
    assert result["error"] == "missing_contact_name"


async def test_handover_to_human(db):
    result = await tools.dispatch_tool(
        "handover_to_human", WA_ID, {"reason": "quiere hablar con alguien"}
    )
    assert result["ok"] is True
    assert "handover_id" in result


async def test_unknown_tool(db):
    result = await tools.dispatch_tool("does_not_exist", WA_ID, {})
    assert result["error"] == "unknown_tool"
