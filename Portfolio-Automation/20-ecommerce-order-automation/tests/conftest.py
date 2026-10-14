"""Fixtures globales para pytest."""

import os

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import InMemoryRepository, set_repository
from app.main import app

# Forzar modo testing
settings.TESTING = True


@pytest.fixture(autouse=True)
def reset_db():
    """Restablece el repositorio en memoria antes de cada test para garantizar aislamiento total."""
    repo = InMemoryRepository()
    set_repository(repo)
    return repo


@pytest.fixture
def client():
    """Cliente HTTP de prueba para interactuar con la aplicación FastAPI."""
    return TestClient(app, follow_redirects=False)


@pytest.fixture
def authenticated_client(client):
    """Cliente HTTP de prueba con cookie de sesión administrativa pre-autenticada."""
    from app.security import create_session_token

    token = create_session_token(settings.ADMIN_USERNAME, settings.SECRET_KEY)
    client.cookies.set("cafe_admin_session", token)
    return client


@pytest.fixture
def sample_payloads():
    """Carga los payloads JSON de muestra de WooCommerce, Shopify y Stripe."""
    samples_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "samples")

    with open(os.path.join(samples_dir, "woocommerce_order_created.json"), "rb") as f:
        wc_bytes = f.read()

    with open(os.path.join(samples_dir, "shopify_orders_create.json"), "rb") as f:
        shopify_bytes = f.read()

    with open(os.path.join(samples_dir, "stripe_payment_intent_succeeded.json"), "rb") as f:
        stripe_bytes = f.read()

    return {
        "wc_bytes": wc_bytes,
        "shopify_bytes": shopify_bytes,
        "stripe_bytes": stripe_bytes,
    }
