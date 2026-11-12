import secrets

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

security = HTTPBearer(auto_error=False)


def verify_dev_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str:
    if (
        credentials is None
        or not settings.DEV_API_KEY
        or not secrets.compare_digest(credentials.credentials, settings.DEV_API_KEY)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


def mask_wa_id(wa_id: str) -> str:
    """Mask a WhatsApp phone id for logs (DECISIONES-13 W3).

    e.g. "573001234567" -> "57300***4567".
    """
    if len(wa_id) <= 9:
        return "*" * len(wa_id)
    return f"{wa_id[:5]}***{wa_id[-4:]}"


def verify_admin_api_key(authorization: str = Header(None)) -> None:
    if not settings.ADMIN_API_KEY:
        raise HTTPException(status_code=500, detail="ADMIN_API_KEY no configurada")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Falta el token Bearer")
    token = authorization.split(" ")[1]
    if not secrets.compare_digest(token, settings.ADMIN_API_KEY):
        raise HTTPException(status_code=401, detail="Token incorrecto")
