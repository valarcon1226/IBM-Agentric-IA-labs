"""Punto de entrada principal de la aplicación FastAPI para Café de Origen."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.database import get_repository
from app.routes import admin, health, webhooks


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida de la aplicación: inicialización de BD y recursos."""
    repo = get_repository()
    await repo.init_db()
    yield
    await repo.close()


app = FastAPI(
    title="Café de Origen - Automatización de Pedidos E-commerce",
    description="Fulfillment centralizado para Shopify, WooCommerce y Stripe con persistencia en MongoDB y panel administrativo.",
    version=__version__,
    lifespan=lifespan,
)

# Servir archivos estáticos (CSS)
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Registrar routers
app.include_router(health.router)
app.include_router(webhooks.router)
app.include_router(admin.router)


@app.get("/", include_in_schema=False)
async def root():
    """Redirección predeterminada al panel de pedidos."""
    return RedirectResponse(url="/admin/orders")
