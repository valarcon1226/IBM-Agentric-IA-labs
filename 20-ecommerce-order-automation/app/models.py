"""Modelos de datos normalizados para productos, clientes, pedidos y eventos."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class OrderStatus(str, Enum):
    """Estados del ciclo de vida de un pedido unificado."""

    PENDIENTE = "pendiente"
    PAGADO = "pagado"
    LISTO_PARA_DESPACHAR = "listo_para_despachar"
    DESPACHADO = "despachado"
    ENTREGADO = "entregado"
    CANCELADO = "cancelado"


class PaymentStatus(str, Enum):
    """Estado del pago."""

    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"


class OrderSource(str, Enum):
    """Plataforma origen del pedido."""

    WOOCOMMERCE = "woocommerce"
    SHOPIFY = "shopify"
    STRIPE = "stripe"
    MANUAL = "manual"


class Product(BaseModel):
    """Modelo de catálogo para Café de Origen."""

    sku: str
    name: str
    description: str
    price: float
    currency: str = "COP"
    stock: int = 100
    es_ficticio: bool = True
    origin: str
    roast: str
    notes: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ShippingAddress(BaseModel):
    """Dirección física para despacho del pedido."""

    street: str = ""
    city: str = ""
    state: str = ""
    postal_code: str = ""
    country: str = "CO"


class Customer(BaseModel):
    """Información del cliente normalizada."""

    name: str
    email: str
    phone: str = ""
    shipping_address: ShippingAddress = Field(default_factory=ShippingAddress)


class OrderItem(BaseModel):
    """Línea de pedido individual."""

    sku: str
    title: str
    quantity: int
    unit_price: float
    total_price: float


class StatusHistoryEntry(BaseModel):
    """Registro histórico de transiciones de estado."""

    from_status: str
    to_status: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    note: str = ""


class Order(BaseModel):
    """Pedido unificado y normalizado para todas las plataformas."""

    id: str
    external_id: str
    source: OrderSource
    status: OrderStatus = OrderStatus.PENDIENTE
    payment_status: PaymentStatus = PaymentStatus.PENDING
    customer: Customer
    items: List[OrderItem] = Field(default_factory=list)
    total_amount: float
    currency: str = "COP"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    history: List[StatusHistoryEntry] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WebhookEvent(BaseModel):
    """Registro de evento recibido para auditoría e idempotencia."""

    event_id: str
    source: OrderSource
    event_type: str
    payload_hash: str
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    order_id: Optional[str] = None
    processed: bool = False
    details: Dict[str, Any] = Field(default_factory=dict)
