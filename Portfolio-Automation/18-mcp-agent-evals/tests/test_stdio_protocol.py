"""Real MCP protocol test: spawn the server on stdio and talk to it with the SDK client."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.asyncio
async def test_stdio_lists_tools_and_calls_one(tmp_path: Path):
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "app.server", "--transport", "stdio"],
        cwd=str(ROOT),
        env={"DATABASE_PATH": str(tmp_path / "stdio.db"), "PYTHONIOENCODING": "utf-8"},
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        names = {t.name for t in (await session.list_tools()).tools}
        assert {
            "consultar_menu",
            "consultar_horario",
            "crear_reserva",
            "estado_pedido",
            "zonas_domicilio",
        } <= names
        result = await session.call_tool("consultar_horario", {"dia": "sabado"})
        assert not result.is_error
        assert "12:00" in result.content[0].text
