"""Mecanismos de seguridad: verificación de firmas de webhooks, hash de contraseñas,

sesiones seguras, CSRF y mitigación de fuerza bruta con bloqueo temporal.
"""

import base64
import hashlib
import hmac
import logging
import secrets
import time
from typing import Dict, Optional, Tuple

import stripe

logger = logging.getLogger("cafe_de_origen.security")

# Diccionario en memoria para rastrear intentos fallidos de login
# Formato: {identifier: (failed_count, lockout_until_timestamp)}
_login_attempts: Dict[str, Tuple[int, float]] = {}

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_SECONDS = 900  # 15 minutos


# ==========================================================
# 1. HASH Y VERIFICACIÓN DE CONTRASEÑAS (PBKDF2-HMAC-SHA256)
# ==========================================================


def hash_password(plain_password: str) -> str:
    """Genera un hash seguro PBKDF2-HMAC-SHA256 con salt aleatorio de 16 bytes."""
    salt = secrets.token_bytes(16)
    from app.config import settings

    iterations = 1_000 if settings.TESTING else 600_000
    derived = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, iterations)
    salt_b64 = base64.b64encode(salt).decode("ascii")
    derived_b64 = base64.b64encode(derived).decode("ascii")
    return f"pbkdf2:sha256:{iterations}${salt_b64}${derived_b64}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica una contraseña contra su hash PBKDF2 en tiempo constante."""
    try:
        parts = hashed_password.split("$")
        if len(parts) != 3:
            return False
        header, salt_b64, derived_b64 = parts
        _, _, iterations_str = header.split(":")
        iterations = int(iterations_str)
        salt = base64.b64decode(salt_b64.encode("ascii"))
        expected_derived = base64.b64decode(derived_b64.encode("ascii"))

        actual_derived = hashlib.pbkdf2_hmac(
            "sha256", plain_password.encode("utf-8"), salt, iterations
        )
        return hmac.compare_digest(actual_derived, expected_derived)
    except Exception as e:
        logger.error("Error verificando hash de contraseña: %s", e)
        return False


# ==========================================================
# 2. TOKENS DE SESIÓN FIRMADOS
# ==========================================================


def create_session_token(username: str, secret_key: str, max_age_seconds: int = 86400) -> str:
    """Genera un token de sesión firmado: username.expires_at.nonce.firma_hmac."""
    expires_at = int(time.time()) + max_age_seconds
    nonce = secrets.token_hex(8)
    message = f"{username}:{expires_at}:{nonce}"
    sig = hmac.new(secret_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
    payload = f"{message}:{sig}"
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")


def verify_session_token(token: str, secret_key: str) -> Optional[str]:
    """Verifica la firma y expiración del token de sesión. Retorna el username o None."""
    try:
        raw = base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
        parts = raw.split(":")
        if len(parts) != 4:
            return None
        username, expires_at_str, nonce, received_sig = parts
        expires_at = int(expires_at_str)
        if time.time() > expires_at:
            return None

        message = f"{username}:{expires_at}:{nonce}"
        expected_sig = hmac.new(
            secret_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        if hmac.compare_digest(received_sig, expected_sig):
            return username
        return None
    except Exception:
        return None


# ==========================================================
# 3. PROTECCIÓN CSRF
# ==========================================================


def create_csrf_token(session_id: str, secret_key: str) -> str:
    """Genera un token CSRF criptográfico ligado a la sesión del usuario."""
    timestamp = int(time.time())
    nonce = secrets.token_hex(8)
    data = f"{session_id}:{timestamp}:{nonce}"
    sig = hmac.new(secret_key.encode("utf-8"), data.encode("utf-8"), hashlib.sha256).hexdigest()
    raw = f"{data}:{sig}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def verify_csrf_token(
    csrf_token: str, session_id: str, secret_key: str, max_age_seconds: int = 7200
) -> bool:
    """Valida un token CSRF frente a la sesión activa en tiempo constante."""
    try:
        raw = base64.urlsafe_b64decode(csrf_token.encode("ascii")).decode("utf-8")
        parts = raw.split(":")
        if len(parts) != 4:
            return False
        token_session, timestamp_str, nonce, received_sig = parts
        if token_session != session_id:
            return False
        timestamp = int(timestamp_str)
        if abs(time.time() - timestamp) > max_age_seconds:
            return False

        data = f"{token_session}:{timestamp}:{nonce}"
        expected_sig = hmac.new(
            secret_key.encode("utf-8"), data.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(received_sig, expected_sig)
    except Exception:
        return False


# ==========================================================
# 4. BLOQUEO TRAS INTENTOS FALLIDOS (RATE LIMITING / BRUTE FORCE)
# ==========================================================


def is_locked_out(identifier: str) -> bool:
    """Verifica si un usuario o IP está actualmente bloqueado por intentos fallidos."""
    now = time.time()
    record = _login_attempts.get(identifier)
    if not record:
        return False
    failed_count, lockout_until = record
    if lockout_until > now:
        return True
    if lockout_until > 0.0 and lockout_until <= now:
        # El tiempo de bloqueo ya expiró, restablecemos
        _login_attempts.pop(identifier, None)
        return False
    return False


def record_failed_attempt(identifier: str) -> Tuple[bool, int]:
    """Registra un fallo. Retorna (está_bloqueado, intentos_restantes)."""
    now = time.time()
    record = _login_attempts.get(identifier)
    if record and record[1] > now:
        return True, 0

    count = (record[0] + 1) if record else 1

    if count >= MAX_FAILED_ATTEMPTS:
        lockout_until = now + LOCKOUT_DURATION_SECONDS
        _login_attempts[identifier] = (count, lockout_until)
        return True, 0

    _login_attempts[identifier] = (count, 0.0)
    return False, MAX_FAILED_ATTEMPTS - count


def reset_failed_attempts(identifier: str) -> None:
    """Limpia el registro de intentos fallidos tras un login exitoso."""
    _login_attempts.pop(identifier, None)


# ==========================================================
# 5. VERIFICACIÓN DE FIRMAS DE WEBHOOKS
# ==========================================================


def verify_woocommerce_signature(
    raw_body: bytes, signature_header: Optional[str], secret: str
) -> bool:
    """Verifica la firma HMAC-SHA256 en Base64 de WooCommerce (x-wc-webhook-signature)."""
    if not signature_header or not secret:
        return False
    try:
        expected = base64.b64encode(
            hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).digest()
        ).decode("ascii")
        return hmac.compare_digest(signature_header.strip(), expected)
    except Exception as e:
        logger.error("Error verificando firma WooCommerce: %s", e)
        return False


def verify_shopify_signature(raw_body: bytes, signature_header: Optional[str], secret: str) -> bool:
    """Verifica la firma HMAC-SHA256 en Base64 de Shopify (X-Shopify-Hmac-Sha256)."""
    if not signature_header or not secret:
        return False
    try:
        expected = base64.b64encode(
            hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).digest()
        ).decode("ascii")
        return hmac.compare_digest(signature_header.strip(), expected)
    except Exception as e:
        logger.error("Error verificando firma Shopify: %s", e)
        return False


def verify_stripe_signature(
    raw_body: bytes, signature_header: Optional[str], secret: str, tolerance_seconds: int = 300
) -> dict:
    """Verifica la firma de Stripe usando la librería oficial con tolerancia temporal.

    Retorna el evento deserializado si es válido, o lanza stripe.error.SignatureVerificationError.
    """
    if not signature_header or not secret:
        raise stripe.error.SignatureVerificationError(
            "Firma o secreto no suministrado", signature_header
        )

    event = stripe.Webhook.construct_event(
        payload=raw_body,
        sig_header=signature_header,
        secret=secret,
        tolerance=tolerance_seconds,
    )
    return event
