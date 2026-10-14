"""Endpoint de verificación de salud para Docker, monitoreo y CI."""

from fastapi import APIRouter

from app import __version__

router = APIRouter(tags=["Salud"])


@router.get("/health", summary="Verificación de salud del servicio")
async def health_check():
    """Retorna estado 200 si la aplicación y sus componentes básicos están operativos."""
    return {
        "status": "healthy",
        "service": "ecommerce-order-automation",
        "version": __version__,
    }
