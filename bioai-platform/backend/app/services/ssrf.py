"""SSRF protection utilities.

Validates that user-supplied URLs point to allowed public hosts and
blocks requests to private/reserved IP ranges.
"""

from __future__ import annotations

import ipaddress
import logging
from urllib.parse import urlparse

from fastapi import HTTPException

logger = logging.getLogger(__name__)

ALLOWED_HOSTS: set[str] = {
    "files.rcsb.org",
    "data.rcsb.org",
    "search.rcsb.org",
    "www.rcsb.org",
    "alphafold.ebi.ac.uk",
    "rest.uniprot.org",
    "www.uniprot.org",
}

PRIVATE_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def validate_url(url: str, param_name: str = "url") -> None:
    """Validate a user-supplied URL against SSRF protections.

    Checks:
    1. URL is well-formed
    2. Host is in the allowlist
    3. Resolved IP is not in a private/reserved range

    Raises HTTPException(400) on violation.
    """
    if not url or not url.strip():
        return

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail=f"{param_name}: only http/https URLs are allowed")

    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(status_code=400, detail=f"{param_name}: invalid URL — no hostname")

    # Check allowlist (suffix match to allow subdomains)
    host_allowed = any(
        hostname == allowed or hostname.endswith("." + allowed)
        for allowed in ALLOWED_HOSTS
    )
    if not host_allowed:
        raise HTTPException(
            status_code=400,
            detail=f"{param_name}: host '{hostname}' is not in the allowed list. "
                   f"Allowed: {', '.join(sorted(ALLOWED_HOSTS))}",
        )

    # Resolve IP and check for private ranges
    try:
        import socket
        addrinfos = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for family, _, _, _, sockaddr in addrinfos:
            ip = ipaddress.ip_address(sockaddr[0])
            for net in PRIVATE_NETWORKS:
                if ip in net:
                    raise HTTPException(
                        status_code=400,
                        detail=f"{param_name}: resolved to private IP {ip} — request blocked",
                    )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"SSRF DNS check failed for {hostname}: {e}")
        # If DNS resolution fails, block the request rather than allowing it through
        raise HTTPException(
            status_code=400,
            detail=f"{param_name}: could not resolve hostname — request blocked",
        )
