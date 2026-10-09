"""Unit tests for app.reminders (DECISIONES-13 W9): send-once-per-reservation reminder logic,
tested by calling `send_due_reminders` directly (no real timer/lifespan involved) against mocked
DB and `send_template`.
"""

import asyncio
import datetime as dt

import pytest

from app import reminders


class FakeConnection:
    def __init__(self, db):
        self.db = db

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def execute(self, statement, params=None):
        return self.db.execute(str(statement), params or {})


class FakeResult:
    def __init__(self, rows=None):
        self._rows = rows or []

    def all(self):
        return self._rows


class FakeEngine:
    def __init__(self, due_rows):
        self.due_rows = due_rows
        self.marked_sent: list[int] = []

    def connect(self):
        return FakeConnection(self)

    def begin(self):
        return FakeConnection(self)

    def execute(self, sql: str, params: dict):
        if "SELECT id, wa_id" in sql:
            return FakeResult(rows=self.due_rows)
        if "UPDATE reservations SET reminder_sent_at" in sql:
            self.marked_sent.append(params["reservation_id"])
            return FakeResult()
        raise AssertionError(f"unexpected query: {sql}")


WA_ID = "573001234567"
DUE_ROW = (1, WA_ID, dt.date(2026, 10, 10), dt.time(19, 0), 4)


async def test_send_due_reminders_sends_template_and_marks_sent(monkeypatch):
    monkeypatch.setattr(reminders.settings, "WHATSAPP_ENABLED", True)
    monkeypatch.setattr(reminders.settings, "REMINDER_TEMPLATE", "hello_world")
    engine = FakeEngine(due_rows=[DUE_ROW])
    monkeypatch.setattr(reminders, "get_engine", lambda: engine)

    sent_calls = []

    async def fake_send_template(wa_id, name, lang, params, **kwargs):
        sent_calls.append((wa_id, name, lang, params))

    monkeypatch.setattr(reminders, "send_template", fake_send_template)

    sent = await reminders.send_due_reminders()

    assert sent == 1
    assert sent_calls == [(WA_ID, "hello_world", "es", ["2026-10-10", "19:00", "4"])]
    assert engine.marked_sent == [1]


async def test_send_due_reminders_dev_mode_only_logs_but_still_marks_sent(monkeypatch):
    monkeypatch.setattr(reminders.settings, "WHATSAPP_ENABLED", False)
    engine = FakeEngine(due_rows=[DUE_ROW])
    monkeypatch.setattr(reminders, "get_engine", lambda: engine)

    calls = []

    async def fake_send_template(wa_id, name, lang, params, **kwargs):
        calls.append(wa_id)

    monkeypatch.setattr(reminders, "send_template", fake_send_template)

    sent = await reminders.send_due_reminders()

    assert sent == 1
    assert calls == []  # never actually called WhatsApp in dev mode
    assert engine.marked_sent == [1]


async def test_send_due_reminders_no_reservations_due(monkeypatch):
    engine = FakeEngine(due_rows=[])
    monkeypatch.setattr(reminders, "get_engine", lambda: engine)

    sent = await reminders.send_due_reminders()

    assert sent == 0
    assert engine.marked_sent == []


async def test_send_due_reminders_send_failure_is_not_marked_sent_and_is_retried_next_tick(
    monkeypatch,
):
    monkeypatch.setattr(reminders.settings, "WHATSAPP_ENABLED", True)
    engine = FakeEngine(due_rows=[DUE_ROW])
    monkeypatch.setattr(reminders, "get_engine", lambda: engine)

    async def failing_send_template(wa_id, name, lang, params, **kwargs):
        raise RuntimeError("WhatsApp API down")

    monkeypatch.setattr(reminders, "send_template", failing_send_template)

    sent = await reminders.send_due_reminders()

    assert sent == 0
    assert engine.marked_sent == []  # not marked: will be retried on the next tick


async def test_reminder_loop_runs_a_pass_then_sleeps(monkeypatch):
    calls = {"passes": 0, "sleeps": 0}

    async def fake_send_due_reminders():
        calls["passes"] += 1
        return 0

    async def fake_sleep(seconds):
        calls["sleeps"] += 1
        assert seconds == reminders.REMINDER_INTERVAL_SECONDS
        raise asyncio.CancelledError  # stop the infinite loop after one iteration

    monkeypatch.setattr(reminders, "send_due_reminders", fake_send_due_reminders)
    monkeypatch.setattr(reminders.asyncio, "sleep", fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        await reminders.reminder_loop()

    assert calls == {"passes": 1, "sleeps": 1}


async def test_reminder_loop_logs_and_continues_after_a_failed_pass(monkeypatch):
    calls = {"passes": 0, "sleeps": 0}

    async def failing_send_due_reminders():
        calls["passes"] += 1
        raise RuntimeError("DB unreachable")

    async def fake_sleep(seconds):
        calls["sleeps"] += 1
        raise asyncio.CancelledError

    monkeypatch.setattr(reminders, "send_due_reminders", failing_send_due_reminders)
    monkeypatch.setattr(reminders.asyncio, "sleep", fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        await reminders.reminder_loop()

    assert calls == {"passes": 1, "sleeps": 1}
