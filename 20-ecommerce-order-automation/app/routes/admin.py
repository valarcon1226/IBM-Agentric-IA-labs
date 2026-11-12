"""Rutas del panel de administración web, autenticación con cookie segura, CSRF y exportación."""

import os
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.database import get_repository
from app.excel_export import export_orders_to_excel
from app.models import OrderStatus
from app.notifications import notify_status_update_email, notify_whatsapp_order_status
from app.security import (
    create_csrf_token,
    create_session_token,
    hash_password,
    is_locked_out,
    record_failed_attempt,
    reset_failed_attempts,
    verify_csrf_token,
    verify_password,
    verify_session_token,
)

router = APIRouter(prefix="/admin", tags=["Administración"])

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

COOKIE_NAME = "cafe_admin_session"
_STORED_ADMIN_HASH: Optional[str] = None


def get_admin_password_hash() -> str:
    """Retorna el hash de la contraseña de admin (generado según entorno/testing)."""
    global _STORED_ADMIN_HASH
    if _STORED_ADMIN_HASH is None or settings.TESTING:
        _STORED_ADMIN_HASH = hash_password(settings.ADMIN_PASSWORD)
    return _STORED_ADMIN_HASH


def get_current_admin(
    cafe_admin_session: Optional[str] = Cookie(None),
) -> str:
    """Dependencia para proteger rutas administrativas verificando la cookie de sesión."""
    if not cafe_admin_session:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/admin/login"},
        )
    username = verify_session_token(cafe_admin_session, settings.SECRET_KEY)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/admin/login"},
        )
    return username


@router.get("", include_in_schema=False)
@router.get("/", include_in_schema=False)
async def admin_root():
    """Redirecciona la raíz de admin hacia la lista de pedidos."""
    return RedirectResponse(url="/admin/orders", status_code=status.HTTP_302_FOUND)


# ==========================================================
# 1. LOGIN / LOGOUT
# ==========================================================
@router.get("/login", response_class=HTMLResponse, summary="Pantalla de inicio de sesión")
async def login_page(
    request: Request,
    cafe_admin_session: Optional[str] = Cookie(None),
):
    """Muestra el formulario de inicio de sesión o redirige si ya hay sesión válida."""
    if cafe_admin_session and verify_session_token(cafe_admin_session, settings.SECRET_KEY):
        return RedirectResponse(url="/admin/orders", status_code=status.HTTP_302_FOUND)

    anon_session_id = request.client.host if request.client else "anon_guest"
    csrf_tok = create_csrf_token(anon_session_id, settings.SECRET_KEY)

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "csrf_token": csrf_tok,
            "current_user": None,
            "error": None,
            "message": None,
        },
    )


@router.post("/login", summary="Procesar credenciales de administrador")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
):
    """Autentica al administrador con protección CSRF y mitigación de fuerza bruta."""
    client_ip = request.client.host if request.client else "unknown_ip"
    rate_limit_id = f"{username}:{client_ip}"

    # 1. Verificar bloqueo por fuerza bruta
    if is_locked_out(rate_limit_id):
        csrf_tok = create_csrf_token(client_ip, settings.SECRET_KEY)
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "csrf_token": csrf_tok,
                "current_user": None,
                "error": "Acceso bloqueado temporalmente por demasiados intentos fallidos (15 min). Por favor espere.",
            },
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    # 2. Verificar CSRF
    if not verify_csrf_token(csrf_token, client_ip, settings.SECRET_KEY):
        csrf_tok = create_csrf_token(client_ip, settings.SECRET_KEY)
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "csrf_token": csrf_tok,
                "current_user": None,
                "error": "Token de seguridad CSRF inválido o expirado. Recargue la página.",
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # 3. Validar usuario y contraseña
    is_valid_user = username == settings.ADMIN_USERNAME
    is_valid_pw = verify_password(password, get_admin_password_hash())

    if not (is_valid_user and is_valid_pw):
        locked, remaining = record_failed_attempt(rate_limit_id)
        csrf_tok = create_csrf_token(client_ip, settings.SECRET_KEY)
        if locked:
            msg = "Demasiados intentos fallidos. Su cuenta/IP ha sido bloqueada temporalmente por 15 minutos."
        else:
            msg = f"Credenciales incorrectas. Le quedan {remaining} intento(s) antes del bloqueo temporal."
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "csrf_token": csrf_tok,
                "current_user": None,
                "error": msg,
            },
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    # Login exitoso: restablecer intentos y crear cookie de sesión segura
    reset_failed_attempts(rate_limit_id)
    session_token = create_session_token(username, settings.SECRET_KEY)

    response = RedirectResponse(url="/admin/orders", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key=COOKIE_NAME,
        value=session_token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=86400,
    )
    return response


@router.get("/logout", summary="Cerrar sesión")
async def logout():
    """Elimina la cookie de sesión y redirige al login."""
    response = RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(COOKIE_NAME)
    return response


# ==========================================================
# 2. LISTA DE PEDIDOS Y MÉTRICAS
# ==========================================================
@router.get("/orders", response_class=HTMLResponse, summary="Panel principal de pedidos")
async def list_orders_view(
    request: Request,
    status: Optional[str] = None,
    source: Optional[str] = None,
    search: Optional[str] = None,
    current_user: str = Depends(get_current_admin),
):
    """Muestra la tabla de pedidos consolidados con filtros y métricas."""
    repo = get_repository()
    orders = await repo.list_orders(status=status, source=source, search=search)

    # Calcular métricas consolidadas sobre el universo total
    all_orders = await repo.list_orders()
    total_count = len(all_orders)
    ready_count = sum(1 for o in all_orders if o.status.value == "listo_para_despachar")
    shipped_count = sum(1 for o in all_orders if o.status.value == "despachado")
    delivered_count = sum(1 for o in all_orders if o.status.value == "entregado")
    total_revenue = sum(o.total_amount for o in all_orders if o.payment_status.value == "paid")

    return templates.TemplateResponse(
        request=request,
        name="orders.html",
        context={
            "current_user": current_user,
            "active_page": "orders",
            "orders": orders,
            "total_count": total_count,
            "ready_count": ready_count,
            "shipped_count": shipped_count,
            "delivered_count": delivered_count,
            "total_revenue": total_revenue,
            "current_status": status,
            "current_source": source,
            "current_search": search,
        },
    )


# ==========================================================
# 3. EXPORTACIÓN A EXCEL (.XLSX) - Ruta específica ANTES de {order_id}
# ==========================================================
@router.get("/orders/export", summary="Exportar pedidos filtrados a Excel")
async def export_orders_excel(
    status: Optional[str] = None,
    source: Optional[str] = None,
    search: Optional[str] = None,
    current_user: str = Depends(get_current_admin),
):
    """Genera y descarga un archivo .xlsx con los pedidos filtrados."""
    repo = get_repository()
    orders = await repo.list_orders(status=status, source=source, search=search)

    excel_bytes = export_orders_to_excel(orders)

    return StreamingResponse(
        iter([excel_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=pedidos_cafe_de_origen.xlsx"},
    )


# ==========================================================
# 4. DETALLE Y TRANSICIÓN DE ESTADOS
# ==========================================================
@router.get("/orders/{order_id}", response_class=HTMLResponse, summary="Detalle de un pedido")
async def order_detail_view(
    request: Request,
    order_id: str,
    message: Optional[str] = None,
    current_user: str = Depends(get_current_admin),
):
    """Muestra el detalle completo del pedido, productos, cliente y formulario de estado."""
    repo = get_repository()
    order = await repo.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    csrf_tok = create_csrf_token(current_user, settings.SECRET_KEY)

    return templates.TemplateResponse(
        request=request,
        name="order_detail.html",
        context={
            "current_user": current_user,
            "active_page": "orders",
            "order": order,
            "csrf_token": csrf_tok,
            "message": message,
        },
    )


@router.post("/orders/{order_id}/status", summary="Actualizar estado del pedido")
async def update_order_status_submit(
    request: Request,
    order_id: str,
    new_status: str = Form(...),
    note: str = Form(""),
    csrf_token: str = Form(...),
    current_user: str = Depends(get_current_admin),
):
    """Cambia el estado de un pedido y notifica al cliente por Email (SMTP) y WhatsApp."""
    # 1. Validar CSRF
    if not verify_csrf_token(csrf_token, current_user, settings.SECRET_KEY):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token CSRF inválido")

    try:
        target_status = OrderStatus(new_status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Estado '{new_status}' no válido") from e

    repo = get_repository()
    order = await repo.update_order_status(order_id, target_status, note=note)
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    # Enviar notificaciones de actualización al cliente
    notify_status_update_email(order, target_status.value, note)
    notify_whatsapp_order_status(order, target_status.value, note)

    return RedirectResponse(
        url=f"/admin/orders/{order_id}?message=Estado+actualizado+exitosamente+y+cliente+notificado",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# ==========================================================
# 5. CATÁLOGO DE PRODUCTOS FICTICIOS
# ==========================================================
@router.get("/products", response_class=HTMLResponse, summary="Catálogo de productos")
async def list_products_view(
    request: Request,
    current_user: str = Depends(get_current_admin),
):
    """Muestra el catálogo de los 8-10 cafés especiales ficticios de Café de Origen."""
    repo = get_repository()
    products = await repo.list_products()

    return templates.TemplateResponse(
        request=request,
        name="products.html",
        context={
            "current_user": current_user,
            "active_page": "products",
            "products": products,
        },
    )
