"""Pruebas de autenticación del panel /admin: login, sesión segura, cookie y bloqueo por fuerza bruta."""

from app.config import settings
from app.security import create_csrf_token, reset_failed_attempts


def test_unauthenticated_access_redirects(client):
    """Acceder sin cookie de sesión a /admin/orders debe redirigir a /admin/login."""
    response = client.get("/admin/orders")
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"


def test_login_success(client):
    """Iniciar sesión con usuario y contraseña correctos debe generar cookie y redirigir."""
    csrf_token = create_csrf_token("testclient", settings.SECRET_KEY)

    response = client.post(
        "/admin/login",
        data={
            "username": settings.ADMIN_USERNAME,
            "password": settings.ADMIN_PASSWORD,
            "csrf_token": csrf_token,
        },
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/orders"
    assert "cafe_admin_session" in response.cookies


def test_login_invalid_password(client):
    """Iniciar sesión con contraseña errónea debe rechazar con 401."""
    # Asegurar que no esté bloqueado antes del test
    reset_failed_attempts(f"{settings.ADMIN_USERNAME}:testclient")

    csrf_token = create_csrf_token("testclient", settings.SECRET_KEY)

    response = client.post(
        "/admin/login",
        data={
            "username": settings.ADMIN_USERNAME,
            "password": "password_totalmente_equivocada",
            "csrf_token": csrf_token,
        },
    )
    assert response.status_code == 401
    assert "incorrectas" in response.text.lower()


def test_brute_force_lockout(client):
    """Cinco intentos fallidos consecutivos deben bloquear la cuenta y responder 429."""
    rate_limit_id = f"{settings.ADMIN_USERNAME}:testclient"
    reset_failed_attempts(rate_limit_id)

    # 5 intentos fallidos
    for _ in range(5):
        csrf_token = create_csrf_token("testclient", settings.SECRET_KEY)
        client.post(
            "/admin/login",
            data={
                "username": settings.ADMIN_USERNAME,
                "password": "bad_password",
                "csrf_token": csrf_token,
            },
        )

    # El 6to intento debe ser bloqueado con 429
    csrf_token = create_csrf_token("testclient", settings.SECRET_KEY)
    response_blocked = client.post(
        "/admin/login",
        data={
            "username": settings.ADMIN_USERNAME,
            "password": settings.ADMIN_PASSWORD,  # Incluso con la clave correcta
            "csrf_token": csrf_token,
        },
    )
    assert response_blocked.status_code == 429
    assert "bloqueado" in response_blocked.text.lower()

    # Limpiar para no afectar otros tests
    reset_failed_attempts(rate_limit_id)


def test_logout(authenticated_client):
    """Cerrar sesión debe eliminar la cookie y redirigir al login."""
    response = authenticated_client.get("/admin/logout")
    assert response.status_code == 302
    assert response.headers["location"] == "/admin/login"
