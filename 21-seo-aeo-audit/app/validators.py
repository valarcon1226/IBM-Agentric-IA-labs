"""URL and IP security validation."""

import ipaddress
import socket
from urllib.parse import urlparse


def is_private_or_loopback_ip(ip_str: str) -> bool:
    """Check if an IP string is private, loopback, link-local, or reserved."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip_str in ("0.0.0.0", "::")
        )
    except ValueError:
        return False


def is_local_hostname(hostname: str) -> bool:
    """Check if hostname indicates a local/internal address."""
    clean = hostname.lower().strip()
    if clean in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        return True
    if clean.endswith(".local") or clean.endswith(".internal") or clean.endswith(".localhost"):
        return True
    return False


def validate_url(url: str, allow_local: bool = False) -> str:
    """
    Validate that the URL has http/https scheme and is not a private/local IP,
    unless allow_local is set to True.
    """
    if not url or not isinstance(url, str):
        raise ValueError("La URL no puede estar vacía.")

    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            f"Esquema de URL no permitido: '{parsed.scheme}'. Solo se admite 'http' o 'https'."
        )

    hostname = parsed.hostname
    if not hostname:
        raise ValueError(f"La URL '{url}' no contiene un nombre de host válido.")

    if not allow_local:
        if is_local_hostname(hostname):
            raise ValueError(
                f"El host '{hostname}' es una dirección local. "
                "Para auditar entornos locales use el parámetro --allow-local."
            )

        if is_private_or_loopback_ip(hostname):
            raise ValueError(
                f"La dirección IP '{hostname}' es privada o de loopback. "
                "Para auditar entornos locales use el parámetro --allow-local."
            )

        # Attempt DNS resolution check to prevent SSRF DNS rebinding to private IPs
        try:
            addr_info = socket.getaddrinfo(hostname, None)
            for item in addr_info:
                resolved_ip = item[4][0]
                if is_private_or_loopback_ip(resolved_ip):
                    raise ValueError(
                        f"El host '{hostname}' resuelve a una IP privada ({resolved_ip}). "
                        "Para auditar entornos locales use el parámetro --allow-local."
                    )
        except socket.gaierror:
            # If DNS fails at validation time, it may still fail during request; allow request layer to handle
            pass

    return url.strip()
