"""Shared request dependencies.

Rate limiting deliberately keys on the network source address. Authentication is
validated separately in ``app.services.auth``. Do not derive a limiter identity by
base64-decoding an unverified JWT: an attacker can mint arbitrary ``sub`` claims
and rotate them to evade per-user quotas.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address


# A verified user-aware limiter can be introduced later via middleware that stores
# an authenticated principal on request.state. Until then IP-based limiting is the
# fail-closed option because it cannot be bypassed by forging JWT payload claims.
limiter = Limiter(key_func=get_remote_address, default_limits=[])
