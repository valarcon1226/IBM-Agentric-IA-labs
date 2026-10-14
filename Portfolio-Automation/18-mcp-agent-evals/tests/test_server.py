"""Tests for MCP server tools, validations, and resource."""

from __future__ import annotations

from app.server import (
    consultar_horario,
    consultar_menu,
    crear_reserva,
    estado_pedido,
    politicas,
    zonas_domicilio,
)


def test_consultar_menu_all():
    res = consultar_menu()
    assert "total" in res
    assert res["total"] >= 15
    assert len(res["platos"]) == res["total"]


def test_consultar_menu_categoria():
    res_entradas = consultar_menu(categoria="entrada")
    assert res_entradas["categoria"] == "entrada"
    assert res_entradas["total"] >= 3
    names = [p["name"] for p in res_entradas["platos"]]
    assert any("Empanadas" in n for n in names)
    assert any("Arepa" in n for n in names)


def test_consultar_menu_plato_existente():
    res = consultar_menu(plato="Bandeja Paisa")
    assert res["encontrado"] is True
    assert res["total"] == 1
    plato = res["platos"][0]
    assert plato["name"] == "Bandeja Paisa"
    assert plato["price_cop"] == 34000
    assert "chicharrón" in plato["description"].lower()


def test_consultar_menu_plato_inexistente():
    res = consultar_menu(plato="Sushi Tempura")
    assert res["encontrado"] is False
    assert "no se encuentra en el menú" in res["mensaje"]
    assert "platos_disponibles" in res


def test_consultar_horario_general():
    res = consultar_horario()
    assert "Martes a domingo" in res["horario_general"]
    assert "Cerrado" in res["lunes"]


def test_consultar_horario_lunes():
    res = consultar_horario(dia="lunes")
    assert res["abierto"] is False
    assert "cerrado" in res["mensaje"].lower()


def test_consultar_horario_dias_abiertos():
    for d in ["martes", "viernes", "sabado", "domingo"]:
        res = consultar_horario(dia=d)
        assert res["abierto"] is True
        assert res["apertura"] == "12:00 m."
        assert res["ultimo_ingreso"] == "8:30 p.m."


def test_consultar_horario_festivo():
    res = consultar_horario(dia="festivo")
    assert res["abierto"] is True
    assert "domingo" in res["mensaje"].lower()


def test_crear_reserva_valida():
    res = crear_reserva(
        nombre="Carlos Gomez",
        telefono="3001234567",
        fecha="2026-11-20",
        hora="13:00",
        personas=4,
    )
    assert res["estado"] == "confirmada"
    assert res["personas"] == 4
    assert res["fecha"] == "2026-11-20"
    assert res["hora"] == "13:00"
    assert res["id_reserva"] > 0


def test_crear_reserva_mas_de_12_personas():
    res = crear_reserva(
        nombre="Grupo Grande",
        telefono="3109876543",
        fecha="2026-11-21",
        hora="14:00",
        personas=15,
    )
    assert res.get("error") == "politica_incumplida"
    assert "12 personas" in res["mensaje"]
    assert "evento" in res["mensaje"].lower() or "catering" in res["mensaje"].lower()


def test_crear_reserva_lunes_error():
    # 2026-11-16 is a Monday
    res = crear_reserva(
        nombre="Ana Ruiz",
        telefono="3123456789",
        fecha="2026-11-16",
        hora="13:00",
        personas=2,
    )
    assert res.get("error") == "politica_incumplida"
    assert "cerrado los lunes" in res["mensaje"].lower()


def test_crear_reserva_hora_temprana():
    res = crear_reserva(
        nombre="Pedro",
        telefono="3001112233",
        fecha="2026-11-20",
        hora="10:00",
        personas=2,
    )
    assert res.get("error") == "politica_incumplida"
    assert "12:00" in res["mensaje"]


def test_crear_reserva_hora_tardia():
    res = crear_reserva(
        nombre="Pedro",
        telefono="3001112233",
        fecha="2026-11-20",
        hora="21:30",
        personas=2,
    )
    assert res.get("error") == "politica_incumplida"
    assert "8:30" in res["mensaje"] or "9:00" in res["mensaje"]


def test_crear_reserva_minutos_invalidos():
    res = crear_reserva(
        nombre="Pedro",
        telefono="3001112233",
        fecha="2026-11-20",
        hora="13:15",
        personas=2,
    )
    assert res.get("error") == "politica_incumplida"
    assert "30 minutos" in res["mensaje"]


def test_crear_reserva_fecha_pasada():
    res = crear_reserva(
        nombre="Pedro",
        telefono="3001112233",
        fecha="2020-01-01",
        hora="13:00",
        personas=2,
    )
    assert res.get("error") == "politica_incumplida"
    assert "fechas pasadas" in res["mensaje"].lower()


def test_crear_reserva_anticipacion_excesiva():
    # More than 60 days in the future
    res = crear_reserva(
        nombre="Pedro Pablo",
        telefono="3001112233",
        fecha="2029-12-28",
        hora="13:00",
        personas=2,
    )
    assert res.get("error") == "politica_incumplida"
    assert "60 días" in res["mensaje"]


def test_crear_reserva_capacidad_maxima():
    # Slot allows max 40 persons. Fill with 3 reservations of 12 (36), then 4 (40).
    r1 = crear_reserva("Cliente Uno", "3001112233", "2026-11-20", "15:00", 12)
    assert r1.get("estado") == "confirmada"
    r2 = crear_reserva("Cliente Dos", "3002223344", "2026-11-20", "15:00", 12)
    assert r2.get("estado") == "confirmada"
    r3 = crear_reserva("Cliente Tres", "3003334455", "2026-11-20", "15:00", 12)
    assert r3.get("estado") == "confirmada"
    # Total so far: 36. Try to book 8 -> exceeds 40
    r4 = crear_reserva("Cliente Cuatro", "3004445566", "2026-11-20", "15:00", 8)
    assert r4.get("error") == "capacidad_excedida"
    assert "disponibilidad" in r4.get("mensaje", "").lower()


def test_estado_pedido_existente():
    res = estado_pedido(id_pedido=1)
    assert res["encontrado"] is True
    assert res["id_pedido"] == 1
    assert res["estado"] == "en_preparacion"
    assert "Chapinero" in res["zona"]
    assert "Ajiaco" in res["items"]


def test_estado_pedido_inexistente():
    res = estado_pedido(id_pedido=9999)
    assert res["encontrado"] is False
    assert "No se encontró ningún pedido" in res["mensaje"]


def test_zonas_domicilio_cubierta():
    res = zonas_domicilio(zona="Chapinero")
    assert res["cobertura"] is True
    assert res["zona"] == "Chapinero"
    assert res["costo"] == "$5.000"
    assert "25-35 min" in res["tiempo_estimado"]
    assert res["pedido_minimo"] == "$25.000"


def test_zonas_domicilio_no_cubierta():
    res = zonas_domicilio(zona="Soacha")
    assert res["cobertura"] is False
    assert "fuera de nuestra cobertura" in res["mensaje"]
    assert "recoger" in res["mensaje"].lower()


def test_zonas_domicilio_lista_general():
    res = zonas_domicilio()
    assert "zonas_cubiertas" in res
    assert len(res["zonas_cubiertas"]) >= 4
    assert res["pedido_minimo"] == "$25.000"


def test_recurso_politicas():
    content = politicas()
    assert "# Políticas y Guías de Operación — Sabor de Casa" in content
    assert "Horarios de Atención" in content
    assert "Políticas de Reserva" in content
    assert "Zonas de Domicilio" in content
    assert "Medios de Pago" in content
