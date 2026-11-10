"""SQLite database management for reservations and orders."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def get_default_db_path() -> Path:
    """Return default SQLite database path."""
    env_path = os.getenv("DATABASE_PATH")
    if env_path:
        return Path(env_path)
    base_dir = Path(__file__).resolve().parent.parent / "data"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / "restaurant.db"


def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Open a SQLite connection with row factory enabled."""
    target = (
        Path(db_path)
        if db_path and db_path != ":memory:"
        else (":memory:" if db_path == ":memory:" else get_default_db_path())
    )
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path | str | None = None) -> None:
    """Initialize SQLite database tables and seed sample orders."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS reservas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            telefono TEXT NOT NULL,
            fecha TEXT NOT NULL,
            hora TEXT NOT NULL,
            personas INTEGER NOT NULL,
            estado TEXT NOT NULL DEFAULT 'confirmada',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_telefono TEXT NOT NULL,
            estado TEXT NOT NULL DEFAULT 'en_preparacion',
            total_cop INTEGER NOT NULL,
            direccion TEXT NOT NULL,
            zona TEXT NOT NULL,
            items TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    # Check if orders need seeding
    cursor.execute("SELECT COUNT(*) FROM pedidos")
    count = cursor.fetchone()[0]
    if count == 0:
        seed_orders = [
            (
                1,
                "3001234567",
                "en_preparacion",
                63000,
                "Cra 7 #54-10 Apto 302",
                "Chapinero",
                "Ajiaco Santafereño x1, Bandeja Paisa x1",
            ),
            (
                2,
                "3109876543",
                "en_camino",
                45000,
                "Calle 100 #15-20 Of 501",
                "Suba",
                "Mojarra Frita x1, Limonada de Coco x1",
            ),
            (
                3,
                "3155551234",
                "entregado",
                22000,
                "Calle 45 #20-15 Casa 2",
                "Teusaquillo",
                "Arroz con Pollo x1",
            ),
        ]
        cursor.executemany(
            """
            INSERT INTO pedidos (id, cliente_telefono, estado, total_cop, direccion, zona, items)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            seed_orders,
        )

    conn.commit()
    conn.close()


def crear_reserva_db(
    nombre: str,
    telefono: str,
    fecha: str,
    hora: str,
    personas: int,
    db_path: Path | str | None = None,
) -> dict:
    """Check slot capacity and record a new reservation."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT COALESCE(SUM(personas), 0)
        FROM reservas
        WHERE fecha = ? AND hora = ? AND estado != 'cancelada'
        """,
        (fecha, hora),
    )
    current_booked = cursor.fetchone()[0]
    max_capacity = 40

    if current_booked + personas > max_capacity:
        available = max(0, max_capacity - current_booked)
        conn.close()
        return {
            "error": "capacidad_excedida",
            "mensaje": (
                f"No hay disponibilidad suficiente para {personas} personas en "
                f"{fecha} a las {hora}. Cupos disponibles: {available}."
            ),
        }

    cursor.execute(
        """
        INSERT INTO reservas (nombre, telefono, fecha, hora, personas, estado)
        VALUES (?, ?, ?, ?, ?, 'confirmada')
        """,
        (nombre, telefono, fecha, hora, personas),
    )
    reserva_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {
        "id_reserva": reserva_id,
        "nombre": nombre,
        "telefono": telefono,
        "fecha": fecha,
        "hora": hora,
        "personas": personas,
        "estado": "confirmada",
        "mensaje": (
            f"Reserva #{reserva_id} confirmada con éxito para {personas} personas "
            f"el {fecha} a las {hora}."
        ),
    }


def obtener_reserva_db(id_reserva: int, db_path: Path | str | None = None) -> dict | None:
    """Fetch reservation details by ID."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, nombre, telefono, fecha, hora, personas, estado, created_at
        FROM reservas WHERE id = ?
        """,
        (id_reserva,),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return dict(row)


def obtener_pedido_db(id_pedido: int, db_path: Path | str | None = None) -> dict | None:
    """Fetch order details by ID."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, cliente_telefono, estado, total_cop, direccion, zona, items, created_at
        FROM pedidos WHERE id = ?
        """,
        (id_pedido,),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return dict(row)
