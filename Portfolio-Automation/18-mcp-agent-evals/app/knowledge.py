"""Knowledge loader reading directly from 13-whatsapp-restaurant-assistant/knowledge/."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MenuItem:
    name: str
    description: str
    category: str
    allergens: str
    price_cop: int
    price_text: str
    available: bool = True

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "allergens": self.allergens,
            "price_cop": self.price_cop,
            "price_text": self.price_text,
            "available": self.available,
        }


@dataclass(frozen=True)
class DeliveryZone:
    zone: str
    cost_cop: int
    cost_text: str
    estimated_time: str

    def to_dict(self) -> dict:
        return {
            "zone": self.zone,
            "cost_cop": self.cost_cop,
            "cost_text": self.cost_text,
            "estimated_time": self.estimated_time,
        }


def get_knowledge_dir() -> Path:
    """Resolve the path to 13-whatsapp-restaurant-assistant/knowledge."""
    env_dir = os.getenv("KNOWLEDGE_DIR")
    if env_dir:
        p = Path(env_dir)
        if p.is_dir():
            return p

    # Standard relative location from 18-mcp-agent-evals/app
    candidate = (
        Path(__file__).resolve().parent.parent.parent
        / "13-whatsapp-restaurant-assistant"
        / "knowledge"
    )
    if candidate.is_dir():
        return candidate

    raise FileNotFoundError(f"Knowledge directory not found at: {candidate}")


def load_file_content(filename: str) -> str:
    """Read a specific markdown file from the knowledge directory."""
    path = get_knowledge_dir() / filename
    if not path.is_file():
        raise FileNotFoundError(f"Knowledge file not found: {path}")
    return path.read_text(encoding="utf-8")


def load_all_policies() -> str:
    """Concatenate all policy and information documents into a single text resource."""
    filenames = [
        ("Horarios de Atención", "horarios.md"),
        ("Políticas de Reserva y Cancelación", "reservas_politicas.md"),
        ("Zonas de Domicilio y Costos", "zonas_domicilio.md"),
        ("Medios de Pago", "medios_pago.md"),
        ("Eventos y Catering", "eventos_catering.md"),
        ("Ubicación y Llegada", "ubicacion.md"),
    ]
    parts: list[str] = ["# Políticas y Guías de Operación — Sabor de Casa\n"]
    for title, fname in filenames:
        content = load_file_content(fname).strip()
        parts.append(f"## {title}\n\n{content}\n")
    return "\n---\n\n".join(parts)


def parse_menu() -> list[MenuItem]:
    """Parse menu items directly from menu.md."""
    text = load_file_content("menu.md")
    items: list[MenuItem] = []

    current_category = "plato_fuerte"
    for line in text.splitlines():
        line_strip = line.strip()
        if line_strip.startswith("## Platos fuertes"):
            current_category = "plato_fuerte"
            continue
        elif line_strip.startswith("## Entradas"):
            current_category = "entrada"
            continue
        elif line_strip.startswith("## Postres y bebidas"):
            current_category = "postre"
            continue

        # Check table row
        if (
            line_strip.startswith("|")
            and not line_strip.startswith("|---")
            and "Plato" not in line_strip
        ):
            cols = [c.strip() for c in line_strip.split("|")[1:-1]]
            if len(cols) >= 4:
                name, ingredients, allergens, price_str = cols[0], cols[1], cols[2], cols[3]
                # Extract numeric price
                digits = re.sub(r"[^\d]", "", price_str)
                price_cop = int(digits) if digits else 0

                cat = current_category
                if current_category == "postre":
                    lower_name = name.lower()
                    if "limonada" in lower_name or "jugo" in lower_name:
                        cat = "bebida"

                available = True
                if (
                    "solo fines de semana" in price_str.lower()
                    or "sujeto a disponibilidad" in price_str.lower()
                ):
                    # Marked conditionally available in knowledge
                    available = True

                items.append(
                    MenuItem(
                        name=name,
                        description=ingredients,
                        category=cat,
                        allergens=allergens,
                        price_cop=price_cop,
                        price_text=f"${price_cop:,}".replace(",", "."),
                        available=available,
                    )
                )

    return items


def parse_delivery_zones() -> list[DeliveryZone]:
    """Parse delivery zones and costs directly from zonas_domicilio.md."""
    text = load_file_content("zonas_domicilio.md")
    zones: list[DeliveryZone] = []

    for line in text.splitlines():
        line_strip = line.strip()
        if (
            line_strip.startswith("|")
            and not line_strip.startswith("|---")
            and "Zona" not in line_strip
        ):
            cols = [c.strip() for c in line_strip.split("|")[1:-1]]
            if len(cols) >= 3:
                zone, cost_str, est_time = cols[0], cols[1], cols[2]
                digits = re.sub(r"[^\d]", "", cost_str)
                cost_cop = int(digits) if digits else 0
                zones.append(
                    DeliveryZone(
                        zone=zone,
                        cost_cop=cost_cop,
                        cost_text=cost_str,
                        estimated_time=est_time,
                    )
                )
    return zones
