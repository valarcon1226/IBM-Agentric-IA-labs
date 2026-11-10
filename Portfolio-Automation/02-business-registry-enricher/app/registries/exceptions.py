class RegistryNotFoundError(Exception):
    """The registry confirmed the identifier does not exist (e.g. HTTP 404)."""


class RegistryError(Exception):
    """The registry call failed after exhausting retries (429/5xx, network error, or fault)."""
