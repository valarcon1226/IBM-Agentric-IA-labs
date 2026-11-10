import os

def get_active_profile() -> str:
    """Devuelve el nombre del perfil activo (variable JOBHUNTER_PROFILE), o '' si no hay ninguno."""
    return os.environ.get("JOBHUNTER_PROFILE", "").strip()

def _base_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))

def profile_dir():
    """Devuelve la carpeta del perfil activo (Profiles/<nombre>), creandola si hace falta.
    Si no hay perfil activo, devuelve None (modo legacy: se usa la raiz del repo)."""
    name = get_active_profile()
    if not name:
        return None
    d = os.path.join(_base_dir(), "Profiles", name)
    os.makedirs(d, exist_ok=True)
    os.makedirs(os.path.join(d, "CVs_Listos"), exist_ok=True)
    return d

def resolve(filename: str) -> str:
    """Resuelve un archivo/carpeta de datos (jobs.db, master_profile.json, CVs_Listos) a la
    carpeta del perfil activo si JOBHUNTER_PROFILE esta seteado, o a la raiz del repo si no
    (comportamiento identico al actual, para no romper nada cuando no se usa esta funcion)."""
    d = profile_dir()
    if d is None:
        return os.path.join(_base_dir(), filename)
    return os.path.join(d, filename)
