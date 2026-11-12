"""Unit tests for app.staff (DECISIONES-13 W7): staff-only commands (`/r`, `/bot`, `/pedidos`)
and the handover staff notification. `app.database.get_engine` / `app.tools.deactivate_handover`
/ `app.whatsapp.send_text` are all mocked — no real Postgres or WhatsApp call involved.
"""

import pytest

from app import staff

WA_ID = "573001234567"
STAFF_1 = "573009990001"
STAFF_2 = "573009990002"


@pytest.fixture(autouse=True)
def _staff_numbers(monkeypatch):
    monkeypatch.setattr(staff.settings, "STAFF_WA_IDS", f"{STAFF_1},{STAFF_2}")


def test_is_staff_true_for_configured_number():
    assert staff.is_staff(STAFF_1) is True


def test_is_staff_false_for_unknown_number():
    assert staff.is_staff(WA_ID) is False


# --- notify_staff ---------------------------------------------------------------------------


async def test_notify_staff_sends_to_every_staff_number_when_whatsapp_enabled(monkeypatch):
    monkeypatch.setattr(staff.settings, "WHATSAPP_ENABLED", True)
    sent_to = []

    async def fake_send_text(wa_id, body, **kwargs):
        sent_to.append((wa_id, body))

    monkeypatch.setattr(staff, "send_text", fake_send_text)

    await staff.notify_staff("cliente pide hablar con alguien", WA_ID, "quiero hablar con alguien")

    assert {wa_id for wa_id, _ in sent_to} == {STAFF_1, STAFF_2}
    body = sent_to[0][1]
    assert "cliente pide hablar con alguien" in body
    assert "quiero hablar con alguien" in body
    assert WA_ID not in body  # the customer number must be masked in the staff notification


async def test_notify_staff_logs_only_when_whatsapp_disabled(monkeypatch):
    monkeypatch.setattr(staff.settings, "WHATSAPP_ENABLED", False)
    calls = []

    async def fake_send_text(wa_id, body, **kwargs):
        calls.append(wa_id)

    monkeypatch.setattr(staff, "send_text", fake_send_text)

    await staff.notify_staff("motivo", WA_ID, "resumen")

    assert calls == []  # never actually sent in dev mode


async def test_notify_staff_with_no_staff_numbers_is_a_noop(monkeypatch):
    monkeypatch.setattr(staff.settings, "STAFF_WA_IDS", "")
    monkeypatch.setattr(staff.settings, "WHATSAPP_ENABLED", True)
    calls = []

    async def fake_send_text(wa_id, body, **kwargs):
        calls.append(wa_id)

    monkeypatch.setattr(staff, "send_text", fake_send_text)

    await staff.notify_staff("motivo", WA_ID, "resumen")

    assert calls == []


async def test_notify_staff_send_failure_does_not_raise(monkeypatch):
    monkeypatch.setattr(staff.settings, "WHATSAPP_ENABLED", True)

    async def failing_send_text(wa_id, body, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(staff, "send_text", failing_send_text)

    await staff.notify_staff("motivo", WA_ID, "resumen")  # must not raise


# --- /pedidos ---------------------------------------------------------------------------------


async def test_pedidos_lists_pending_orders(monkeypatch):
    class FakeResult:
        def all(self):
            return [(1, WA_ID, 39000), (2, "573009998888", 25000)]

    class FakeConnection:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return False

        async def execute(self, statement, params=None):
            return FakeResult()

    class FakeEngine:
        def connect(self):
            return FakeConnection()

    monkeypatch.setattr(staff, "get_engine", lambda: FakeEngine())

    replies = await staff.handle_staff_command(STAFF_1, "/pedidos")

    assert len(replies) == 1
    assert "#1" in replies[0]
    assert "#2" in replies[0]


async def test_pedidos_no_pending_orders(monkeypatch):
    class FakeResult:
        def all(self):
            return []

    class FakeConnection:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return False

        async def execute(self, statement, params=None):
            return FakeResult()

    class FakeEngine:
        def connect(self):
            return FakeConnection()

    monkeypatch.setattr(staff, "get_engine", lambda: FakeEngine())

    replies = await staff.handle_staff_command(STAFF_1, "/pedidos")

    assert replies == ["No hay pedidos pendientes hoy."]


# --- /bot ---------------------------------------------------------------------------------


async def test_bot_command_reactivates_the_bot(monkeypatch):
    calls = []

    async def fake_deactivate_handover(wa_id):
        calls.append(wa_id)

    monkeypatch.setattr("app.tools.deactivate_handover", fake_deactivate_handover)

    replies = await staff.handle_staff_command(STAFF_1, f"/bot {WA_ID}")

    assert calls == [WA_ID]
    assert "57300" in replies[0]


async def test_bot_command_without_wa_id_shows_usage():
    replies = await staff.handle_staff_command(STAFF_1, "/bot")
    assert replies == ["Uso: /bot <wa_id>"]


# --- /r -------------------------------------------------------------------------------------


async def test_r_command_sends_message_to_customer(monkeypatch):
    monkeypatch.setattr(staff.settings, "WHATSAPP_ENABLED", True)
    sent = []

    async def fake_send_text(wa_id, body, **kwargs):
        sent.append((wa_id, body))

    monkeypatch.setattr(staff, "send_text", fake_send_text)

    replies = await staff.handle_staff_command(STAFF_1, f"/r {WA_ID} Tu pedido va en camino")

    assert sent == [(WA_ID, "Tu pedido va en camino")]
    assert "57300" in replies[0]


async def test_r_command_without_text_shows_usage():
    replies = await staff.handle_staff_command(STAFF_1, f"/r {WA_ID}")
    assert replies == ["Uso: /r <wa_id> <texto>"]


async def test_r_command_send_failure_reports_error(monkeypatch):
    monkeypatch.setattr(staff.settings, "WHATSAPP_ENABLED", True)

    async def failing_send_text(wa_id, body, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(staff, "send_text", failing_send_text)

    replies = await staff.handle_staff_command(STAFF_1, f"/r {WA_ID} hola")

    assert replies == ["No se pudo enviar el mensaje al cliente."]


# --- unknown command --------------------------------------------------------------------------


async def test_unknown_command_is_reported():
    replies = await staff.handle_staff_command(STAFF_1, "/no-existe")
    assert "no reconocido" in replies[0]
