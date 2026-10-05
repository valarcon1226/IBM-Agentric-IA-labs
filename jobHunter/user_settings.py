"""Preferencias de búsqueda por persona: Profiles/<nombre>/search_settings.json (las crea main.py).
Sin perfil activo o sin archivo se usan los valores de Valentina, así el homelab sigue igual."""
import json
import os

import profile_paths

DEFAULTS = {
    "home_country": "colombia",                                      # país desde donde trabaja (minúsculas)
    "search_locations": ["Colombia", "Latin America", "United States"],  # ubicaciones de LinkedIn a buscar
    "accept_international_contractor": True,                         # empresas de afuera sin pedir permiso de trabajo
    "role_families": ["ai_engineer", "forward_deployed", "qa_automation"],  # ver job_scoring.RoleFamily
    "years_by_family": {"qa_automation": 3, "default": 2},           # años reales por disciplina
    "allowed_langs": "en,es",                                        # idiomas de las vacantes que acepta
    "remote_only": True,                                             # False: también híbrido/presencial en su ciudad
    "cv_language": "en",                                             # "auto" = idioma de cada vacante (amigos)
}

ROLE_FAMILY_LABELS = {
    "ai_engineer": "AI / ML Engineer", "forward_deployed": "Forward Deployed / Solutions Engineer",
    "fullstack": "Full Stack", "backend": "Backend", "frontend": "Frontend", "qa_automation": "QA / Testing",
    "data": "Data (analista, ingeniero, científico)", "devops": "DevOps / Cloud / SRE", "other_technical": "Otro rol técnico",
    "sales_business_development": "Ventas / Desarrollo de negocios / Alianzas", "account_management": "Key Account / Gestión de cuentas",
    "marketing": "Marketing", "operations": "Operaciones / Logística", "finance": "Finanzas", "product": "Producto (Product Manager/Owner)",
    "consulting": "Consultoría", "customer_success": "Customer Success / Servicio al cliente", "human_resources": "Recursos Humanos",
}

_cache = None


def path() -> str:
    return profile_paths.resolve("search_settings.json")


def load() -> dict:
    global _cache
    if _cache is None:
        data = {}
        if profile_paths.get_active_profile() and os.path.exists(path()):
            with open(path(), encoding="utf-8") as f:
                data = json.load(f)
        _cache = {**DEFAULTS, **data}
    return _cache


def get(key: str):
    return load()[key]


def save(settings: dict):
    global _cache
    with open(path(), "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
    _cache = {**DEFAULTS, **settings}
