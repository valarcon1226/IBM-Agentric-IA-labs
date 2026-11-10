"""Capa de persistencia con soporte para MongoDB (Motor) y repositorio en memoria para tests."""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import settings
from app.models import Order, OrderStatus, Product, StatusHistoryEntry, WebhookEvent
from app.seed_data import SEED_PRODUCTS

logger = logging.getLogger("cafe_de_origen.database")


class BaseRepository:
    """Contrato base para el almacenamiento de pedidos, eventos y productos."""

    async def init_db(self) -> None:
        raise NotImplementedError

    async def get_order(self, order_id: str) -> Optional[Order]:
        raise NotImplementedError

    async def find_order_by_external_id(self, source: str, external_id: str) -> Optional[Order]:
        raise NotImplementedError

    async def list_orders(
        self,
        status: Optional[str] = None,
        source: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[Order]:
        raise NotImplementedError

    async def create_order(self, order: Order) -> Order:
        raise NotImplementedError

    async def update_order_status(
        self, order_id: str, new_status: OrderStatus, note: str = ""
    ) -> Optional[Order]:
        raise NotImplementedError

    async def get_event(self, event_id: str, payload_hash: str) -> Optional[WebhookEvent]:
        raise NotImplementedError

    async def create_event(self, event: WebhookEvent) -> WebhookEvent:
        raise NotImplementedError

    async def mark_event_processed(
        self, event_id: str, order_id: str, details: Optional[dict] = None
    ) -> None:
        raise NotImplementedError

    async def list_products(self) -> List[Product]:
        raise NotImplementedError

    async def close(self) -> None:
        pass


class InMemoryRepository(BaseRepository):
    """Implementación rápida en memoria para testing y ejecución sin contenedor local."""

    def __init__(self) -> None:
        self.orders: Dict[str, Order] = {}
        self.events: Dict[str, WebhookEvent] = {}
        self.products: List[Product] = list(SEED_PRODUCTS)

    async def init_db(self) -> None:
        if not self.products:
            self.products = list(SEED_PRODUCTS)

    async def get_order(self, order_id: str) -> Optional[Order]:
        return self.orders.get(order_id)

    async def find_order_by_external_id(self, source: str, external_id: str) -> Optional[Order]:
        for o in self.orders.values():
            if o.source.value == source and o.external_id == external_id:
                return o
        return None

    async def list_orders(
        self,
        status: Optional[str] = None,
        source: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[Order]:
        results = list(self.orders.values())
        if status:
            results = [o for o in results if o.status.value == status]
        if source:
            results = [o for o in results if o.source.value == source]
        if search:
            q = search.lower().strip()
            results = [
                o
                for o in results
                if q in o.id.lower()
                or q in o.external_id.lower()
                or q in o.customer.name.lower()
                or q in o.customer.email.lower()
            ]
        # Ordenar por fecha de creación descendente
        results.sort(key=lambda x: x.created_at, reverse=True)
        return results

    async def create_order(self, order: Order) -> Order:
        self.orders[order.id] = order
        return order

    async def update_order_status(
        self, order_id: str, new_status: OrderStatus, note: str = ""
    ) -> Optional[Order]:
        order = self.orders.get(order_id)
        if not order:
            return None
        old_status = order.status.value
        order.status = new_status
        order.updated_at = datetime.now(timezone.utc)
        order.history.append(
            StatusHistoryEntry(
                from_status=old_status,
                to_status=new_status.value,
                note=note,
            )
        )
        return order

    async def get_event(self, event_id: str, payload_hash: str) -> Optional[WebhookEvent]:
        # Buscar por event_id o por hash idéntico
        if event_id in self.events:
            return self.events[event_id]
        for evt in self.events.values():
            if evt.payload_hash == payload_hash:
                return evt
        return None

    async def create_event(self, event: WebhookEvent) -> WebhookEvent:
        self.events[event.event_id] = event
        return event

    async def mark_event_processed(
        self, event_id: str, order_id: str, details: Optional[dict] = None
    ) -> None:
        if event_id in self.events:
            self.events[event_id].processed = True
            self.events[event_id].order_id = order_id
            if details:
                self.events[event_id].details.update(details)

    async def list_products(self) -> List[Product]:
        return list(self.products)


class MongoRepository(BaseRepository):
    """Implementación oficial con Motor para MongoDB."""

    def __init__(self, uri: str, db_name: str) -> None:
        self.client: AsyncIOMotorClient = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=2500)
        self.db: AsyncIOMotorDatabase = self.client[db_name]

    async def init_db(self) -> None:
        try:
            # Índices únicos
            await self.db.orders.create_index("id", unique=True)
            await self.db.orders.create_index([("source", 1), ("external_id", 1)])
            await self.db.events.create_index("event_id", unique=True)
            await self.db.events.create_index("payload_hash")

            # Sembrar catálogo si está vacío
            count = await self.db.products.count_documents({})
            if count == 0:
                logger.info("Sembrando catálogo de Café de Origen en MongoDB...")
                await self.db.products.insert_many([p.model_dump() for p in SEED_PRODUCTS])
        except Exception as e:
            logger.warning("No se pudo inicializar índices en MongoDB: %s", e)

    async def get_order(self, order_id: str) -> Optional[Order]:
        doc = await self.db.orders.find_one({"id": order_id})
        return Order(**doc) if doc else None

    async def find_order_by_external_id(self, source: str, external_id: str) -> Optional[Order]:
        doc = await self.db.orders.find_one({"source": source, "external_id": external_id})
        return Order(**doc) if doc else None

    async def list_orders(
        self,
        status: Optional[str] = None,
        source: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[Order]:
        query: dict = {}
        if status:
            query["status"] = status
        if source:
            query["source"] = source
        if search:
            regex = {"$regex": search, "$options": "i"}
            query["$or"] = [
                {"id": regex},
                {"external_id": regex},
                {"customer.name": regex},
                {"customer.email": regex},
            ]

        cursor = self.db.orders.find(query).sort("created_at", -1)
        docs = await cursor.to_list(length=500)
        return [Order(**d) for d in docs]

    async def create_order(self, order: Order) -> Order:
        await self.db.orders.insert_one(order.model_dump())
        return order

    async def update_order_status(
        self, order_id: str, new_status: OrderStatus, note: str = ""
    ) -> Optional[Order]:
        existing = await self.get_order(order_id)
        if not existing:
            return None

        old_status = existing.status.value
        entry = StatusHistoryEntry(
            from_status=old_status,
            to_status=new_status.value,
            note=note,
        )
        updated_at = datetime.now(timezone.utc)

        await self.db.orders.update_one(
            {"id": order_id},
            {
                "$set": {
                    "status": new_status.value,
                    "updated_at": updated_at.isoformat(),
                },
                "$push": {"history": entry.model_dump()},
            },
        )
        return await self.get_order(order_id)

    async def get_event(self, event_id: str, payload_hash: str) -> Optional[WebhookEvent]:
        doc = await self.db.events.find_one(
            {"$or": [{"event_id": event_id}, {"payload_hash": payload_hash}]}
        )
        return WebhookEvent(**doc) if doc else None

    async def create_event(self, event: WebhookEvent) -> WebhookEvent:
        await self.db.events.insert_one(event.model_dump())
        return event

    async def mark_event_processed(
        self, event_id: str, order_id: str, details: Optional[dict] = None
    ) -> None:
        update: dict = {
            "$set": {
                "processed": True,
                "order_id": order_id,
            }
        }
        if details:
            for k, v in details.items():
                update["$set"][f"details.{k}"] = v
        await self.db.events.update_one({"event_id": event_id}, update)

    async def list_products(self) -> List[Product]:
        cursor = self.db.products.find({})
        docs = await cursor.to_list(length=100)
        if not docs:
            return list(SEED_PRODUCTS)
        return [Product(**d) for d in docs]

    async def close(self) -> None:
        self.client.close()


# Repositorio global activo
_active_repository: Optional[BaseRepository] = None


def get_repository() -> BaseRepository:
    """Retorna la instancia singleton del repositorio correspondiente."""
    global _active_repository
    if _active_repository is None:
        if settings.TESTING:
            _active_repository = InMemoryRepository()
        else:
            try:
                _active_repository = MongoRepository(settings.MONGO_URI, settings.MONGO_DB_NAME)
            except Exception as e:
                logger.warning("Error conectando a MongoDB (%s), usando repositorio en memoria.", e)
                _active_repository = InMemoryRepository()
    return _active_repository


def set_repository(repo: BaseRepository) -> None:
    """Permite sobrescribir el repositorio (útil en pruebas unitarias)."""
    global _active_repository
    _active_repository = repo
