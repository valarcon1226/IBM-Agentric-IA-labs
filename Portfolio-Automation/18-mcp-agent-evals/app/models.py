"""Pydantic schemas and validation models for Sabor de Casa MCP tools."""

from __future__ import annotations

import os
from datetime import date, time

from pydantic import BaseModel, Field, field_validator


class CrearReservaInput(BaseModel):
    nombre: str = Field(..., min_length=2, description="Nombre completo de la persona que reserva")
    telefono: str = Field(
        ..., min_length=7, description="Número de teléfono o WhatsApp de contacto"
    )
    fecha: str = Field(..., description="Fecha de la reserva en formato AAAA-MM-DD")
    hora: str = Field(..., description="Hora de la reserva en formato HH:MM (ej. 13:00)")
    personas: int = Field(..., description="Número de personas (máximo 12)")

    @field_validator("fecha")
    @classmethod
    def validate_fecha(cls, v: str) -> str:
        try:
            parsed_date = date.fromisoformat(v)
        except ValueError as err:
            raise ValueError("Formato de fecha inválido. Debe ser AAAA-MM-DD.") from err

        # Check not in past
        # Fixed 'today' for tests/evals whose cases use concrete dates; unset in production.
        ref = os.environ.get("RESERVAS_FECHA_REFERENCIA")
        today = date.fromisoformat(ref) if ref else date.today()
        if parsed_date < today:
            raise ValueError("No se pueden realizar reservas para fechas pasadas.")

        # Check max advance of 60 days
        diff_days = (parsed_date - today).days
        if diff_days > 60:
            raise ValueError(
                f"No se pueden realizar reservas con más de 60 días de anticipación "
                f"(solicitado: {diff_days} días)."
            )

        # Day of week: Monday is 0
        if parsed_date.weekday() == 0:
            raise ValueError(
                "El restaurante está cerrado los lunes (descanso del equipo de cocina). "
                "Por favor selecciona una fecha entre martes y domingo."
            )

        return v

    @field_validator("hora")
    @classmethod
    def validate_hora(cls, v: str) -> str:
        parts = v.strip().split(":")
        if len(parts) < 2:
            raise ValueError("Formato de hora inválido. Debe ser HH:MM (ej. 13:00 o 19:30).")

        try:
            hour = int(parts[0])
            minute = int(parts[1])
            t = time(hour, minute)
        except ValueError as err:
            raise ValueError("Hora no válida. Debe estar entre 00:00 y 23:59.") from err

        # Operating hours: 12:00 to 21:00, last entry 20:30
        open_time = time(12, 0)
        last_entry = time(20, 30)

        if t < open_time:
            raise ValueError(
                "El restaurante abre a las 12:00 m. No se aceptan reservas antes de esa hora."
            )
        if t > last_entry:
            raise ValueError(
                "El restaurante cierra a las 9:00 p.m. y el último ingreso permitido es a "
                "las 8:30 p.m."
            )

        if minute not in (0, 30):
            raise ValueError(
                "Las reservas deben realizarse en franjas de 30 minutos (ej. 13:00 o 13:30)."
            )

        return f"{hour:02d}:{minute:02d}"

    @field_validator("personas")
    @classmethod
    def validate_personas(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("El número de personas debe ser mayor a 0.")
        if v > 12:
            raise ValueError(
                "El tamaño máximo por reserva de mesa es de 12 personas. "
                "Para grupos de más de 12 personas, por favor comuníquese para gestionar "
                "su solicitud como evento o servicio de catering."
            )
        return v


class ConsultarMenuInput(BaseModel):
    categoria: str | None = Field(
        None,
        description="Categoría a filtrar: plato_fuerte, entrada, postre, bebida",
    )
    plato: str | None = Field(
        None,
        description="Nombre o parte del nombre del plato a consultar",
    )


class ConsultarHorarioInput(BaseModel):
    dia: str | None = Field(
        None,
        description="Día de la semana a consultar (ej. lunes, martes, sábado, festivo)",
    )


class EstadoPedidoInput(BaseModel):
    id_pedido: int = Field(..., gt=0, description="Identificador numérico del pedido")


class ZonasDomicilioInput(BaseModel):
    zona: str | None = Field(
        None,
        description="Nombre de la zona o barrio en Bogotá para verificar cobertura y costo",
    )
