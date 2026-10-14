"""Servicio de notificaciones para clientes: Correo vía SMTP (Mailpit) y WhatsApp

mediante interfaz intercambiable (Stub para demo y Cloud API para producción).
"""

import logging
import smtplib
from email.message import EmailMessage
from typing import Optional, Protocol

import httpx

from app.config import settings
from app.models import Order

logger = logging.getLogger("cafe_de_origen.notifications")


# ==========================================================
# 1. NOTIFICACIONES POR CORREO ELECTRÓNICO (SMTP)
# ==========================================================


def send_email(
    to_email: str,
    subject: str,
    text_content: str,
    html_content: Optional[str] = None,
    smtp_host: Optional[str] = None,
    smtp_port: Optional[int] = None,
    from_email: Optional[str] = None,
) -> bool:
    """Envía un correo electrónico mediante SMTP (compatible con Mailpit)."""
    host = smtp_host or settings.SMTP_HOST
    port = smtp_port or settings.SMTP_PORT
    sender = from_email or settings.SMTP_FROM

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_email
    msg.set_content(text_content)

    if html_content:
        msg.add_alternative(html_content, subtype="html")

    try:
        with smtplib.SMTP(host, port, timeout=5.0) as server:
            server.send_message(msg)
        logger.info("Correo enviado exitosamente a %s [Asunto: %s]", to_email, subject)
        return True
    except Exception as e:
        logger.warning(
            "No se pudo enviar correo vía SMTP a %s:%s para %s: %s", host, port, to_email, e
        )
        return False


def notify_order_ready_for_dispatch(order: Order) -> bool:
    """Envía correo de confirmación de pago y estado 'listo para despachar'."""
    subject = f"¡Tu pedido {order.id} está listo para despachar! - Café de Origen"

    items_list_txt = "\n".join(
        [
            f" - {it.quantity}x {it.title} (${it.total_price:,.0f} {order.currency})"
            for it in order.items
        ]
    )
    text_content = f"""Hola {order.customer.name},

¡Buenas noticias! Tu pedido {order.id} ha sido confirmado y su pago ha sido verificado con éxito.
Actualmente el pedido se encuentra LISTO PARA DESPACHAR.

Resumen del Pedido:
{items_list_txt}

Total Pagado: ${order.total_amount:,.0f} {order.currency}
Dirección de Entrega: {order.customer.shipping_address.street}, {order.customer.shipping_address.city}

Te avisaremos tan pronto el mensajero retire tu paquete.

Atentamente,
El equipo de Café de Origen ☕
"""

    items_rows_html = "".join(
        [
            f"<tr><td style='padding:8px;border-bottom:1px solid #ddd;'>{it.quantity}x {it.title}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #ddd;text-align:right;'>${it.total_price:,.0f}</td></tr>"
            for it in order.items
        ]
    )

    html_content = f"""<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6; max-width: 600px; margin: 0 auto; padding: 20px;">
  <div style="background-color: #3e2723; color: #fff; padding: 20px; text-align: center; border-radius: 8px 8px 0 0;">
    <h1 style="margin: 0; font-size: 24px;">☕ Café de Origen</h1>
    <p style="margin: 5px 0 0 0; font-size: 14px;">Automatización de Pedidos</p>
  </div>
  <div style="background: #fafafa; border: 1px solid #eee; padding: 20px; border-radius: 0 0 8px 8px;">
    <h2>¡Hola {order.customer.name}!</h2>
    <p>Confirmamos la recepción de tu pago. Tu pedido <strong>{order.id}</strong> está <strong>LISTO PARA DESPACHAR</strong>.</p>

    <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
      <thead>
        <tr style="background: #eceff1;">
          <th style="padding: 8px; text-align: left;">Producto</th>
          <th style="padding: 8px; text-align: right;">Total</th>
        </tr>
      </thead>
      <tbody>
        {items_rows_html}
        <tr>
          <td style="padding: 12px 8px; font-weight: bold;">Total:</td>
          <td style="padding: 12px 8px; font-weight: bold; text-align: right;">${order.total_amount:,.0f} {order.currency}</td>
        </tr>
      </tbody>
    </table>

    <p style="background: #e8f5e9; border-left: 4px solid #4caf50; padding: 12px;">
      📍 <strong>Dirección de Entrega:</strong><br>
      {order.customer.shipping_address.street}, {order.customer.shipping_address.city}, {order.customer.shipping_address.state}
    </p>

    <p style="font-size: 13px; color: #777; margin-top: 30px;">
      Nota: Este es un correo automático generado por el sistema de demostración de Café de Origen.
    </p>
  </div>
</body>
</html>"""

    return send_email(order.customer.email, subject, text_content, html_content)


def notify_status_update_email(order: Order, new_status: str, note: str = "") -> bool:
    """Envía correo al cliente cuando el estado de su pedido avanza."""
    status_label = {
        "despachado": "EN CAMINO (Despachado)",
        "entregado": "ENTREGADO con éxito",
        "cancelado": "CANCELADO",
    }.get(new_status, new_status.upper())

    subject = f"Actualización de tu pedido {order.id}: {status_label} - Café de Origen"
    text_content = f"""Hola {order.customer.name},

El estado de tu pedido {order.id} ha cambiado a: {status_label}.
{f"Nota adicional: {note}" if note else ""}

Detalles del Pedido:
Total: ${order.total_amount:,.0f} {order.currency}
Destino: {order.customer.shipping_address.street}, {order.customer.shipping_address.city}

Gracias por confiar en el mejor café colombiano de Café de Origen.
"""
    return send_email(order.customer.email, subject, text_content)


# ==========================================================
# 2. NOTIFICACIONES POR WHATSAPP (INTERFAZ + STUB + CLOUD API)
# ==========================================================


class WhatsAppNotifier(Protocol):
    """Protocolo / Interfaz para el despachador de WhatsApp."""

    def send_message(self, to_phone: str, message: str) -> bool:
        """Envía un mensaje de texto por WhatsApp al teléfono especificado."""
        ...


class LogWhatsAppNotifier:
    """Implementación de demostración (Stub) que registra en log estructurado."""

    def send_message(self, to_phone: str, message: str) -> bool:
        clean_phone = to_phone.strip() if to_phone else "No proporcionado"
        logger.info("[WHATSAPP NOTIFICACIÓN] Para: %s | Mensaje:\n%s", clean_phone, message)
        return True


class CloudApiWhatsAppNotifier:
    """Implementación para WhatsApp Cloud API oficial (Meta for Developers)."""

    def __init__(self, api_token: str, phone_number_id: str) -> None:
        self.api_token = api_token
        self.phone_number_id = phone_number_id
        self.endpoint = f"https://graph.facebook.com/v20.0/{self.phone_number_id}/messages"

    def send_message(self, to_phone: str, message: str) -> bool:
        if not to_phone:
            logger.warning("No se puede enviar WhatsApp: teléfono vacío.")
            return False

        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_phone.replace("+", "").strip(),
            "type": "text",
            "text": {"preview_url": False, "body": message},
        }
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(self.endpoint, headers=headers, json=payload)
                if res.status_code in (200, 201):
                    logger.info("WhatsApp Cloud API enviado a %s: %s", to_phone, res.json())
                    return True
                logger.error("Error enviando WhatsApp Cloud API: %s %s", res.status_code, res.text)
                return False
        except Exception as e:
            logger.error("Excepción al conectar con WhatsApp Cloud API: %s", e)
            return False


def get_whatsapp_notifier() -> WhatsAppNotifier:
    """Fabrica la instancia de WhatsApp adecuada según la configuración disponible."""
    if settings.WHATSAPP_API_TOKEN and settings.WHATSAPP_PHONE_NUMBER_ID:
        return CloudApiWhatsAppNotifier(
            settings.WHATSAPP_API_TOKEN, settings.WHATSAPP_PHONE_NUMBER_ID
        )
    return LogWhatsAppNotifier()


def notify_whatsapp_order_status(order: Order, status: str, note: str = "") -> bool:
    """Envía la notificación correspondiente por WhatsApp al cliente."""
    notifier = get_whatsapp_notifier()
    phone = order.customer.phone
    if not phone:
        logger.info("El pedido %s no tiene teléfono para WhatsApp.", order.id)
        return False

    status_messages = {
        "listo_para_despachar": f"☕ *Café de Origen*: Hola {order.customer.name}, tu pedido *{order.id}* por ${order.total_amount:,.0f} {order.currency} ha sido confirmado y está *LISTO PARA DESPACHAR*. Te avisaremos cuando salga de bodega.",
        "despachado": f"🚚 *Café de Origen*: ¡Tu pedido *{order.id}* va en camino! Nuestro mensajero se dirige a {order.customer.shipping_address.street}, {order.customer.shipping_address.city}.",
        "entregado": f"🎉 *Café de Origen*: Tu pedido *{order.id}* ha sido marcado como *ENTREGADO*. ¡Disfruta del mejor café de Colombia!",
    }

    msg = status_messages.get(
        status,
        f"☕ *Café de Origen*: El estado de tu pedido *{order.id}* se actualizó a *{status}*. {note}",
    )
    return notifier.send_message(phone, msg)
