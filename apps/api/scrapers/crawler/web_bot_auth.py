"""Web Bot Auth: HTTP Message Signatures (RFC 9421) with an Ed25519 key."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from urllib.parse import urlsplit

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

AGENT = "https://baboom.com.br"
USER_AGENT = f"BaboomBot/1.0 (+{AGENT})"
DIRECTORY_PATH = "/.well-known/http-message-signatures-directory"
DIRECTORY_CONTENT_TYPE = "application/http-message-signatures-directory+json"
VALIDITY_SECONDS = 60
DEFAULT_PORTS = {"http": 80, "https": 443}


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def load_private_key(seed: str) -> Ed25519PrivateKey:
    """Read a key from its 32-byte seed, base64url encoded."""
    raw = base64.urlsafe_b64decode(seed + "=" * (-len(seed) % 4))
    return Ed25519PrivateKey.from_private_bytes(raw)


def public_jwk(key: Ed25519PrivateKey) -> dict[str, str]:
    """Return the key's public half as an OKP JWK (RFC 8037)."""
    raw = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return {"kty": "OKP", "crv": "Ed25519", "x": _b64url(raw)}


def thumbprint(jwk: dict[str, str]) -> str:
    """Return the JWK thumbprint (RFC 7638), the signature's ``keyid``."""
    members = {name: jwk[name] for name in ("crv", "kty", "x")}
    canonical = json.dumps(members, separators=(",", ":"), sort_keys=True)
    return _b64url(hashlib.sha256(canonical.encode()).digest())


def authority(url: str) -> str:
    """Return the ``@authority`` of a URL: host, with a non-default port."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.port is not None and parts.port != DEFAULT_PORTS.get(parts.scheme):
        return f"{host}:{parts.port}"
    return host


def _signed(
    key: Ed25519PrivateKey,
    components: dict[str, str],
    tag: str,
    created: int,
) -> dict[str, str]:
    """Sign the components; return ``Signature-Input`` and ``Signature``."""
    nonce = base64.b64encode(secrets.token_bytes(32)).decode("ascii")
    params = (
        f"({' '.join(components)});created={created}"
        f";expires={created + VALIDITY_SECONDS}"
        f';keyid="{thumbprint(public_jwk(key))}";alg="ed25519"'
        f';nonce="{nonce}";tag="{tag}"'
    )
    lines = [f"{name}: {value}" for name, value in components.items()]
    base = "\n".join([*lines, f'"@signature-params": {params}'])
    signature = base64.b64encode(key.sign(base.encode("ascii"))).decode("ascii")
    return {"Signature-Input": f"sig1={params}", "Signature": f"sig1=:{signature}:"}


def request_headers(key: Ed25519PrivateKey, url: str, created: int) -> dict[str, str]:
    """Return the headers that sign a request to ``url``."""
    agent = f'"{AGENT}"'
    components = {'"@authority"': authority(url), '"signature-agent"': agent}
    return {
        "Signature-Agent": agent,
        **_signed(key, components, "web-bot-auth", created),
    }


def directory(
    key: Ed25519PrivateKey,
    host: str,
    created: int,
) -> tuple[str, dict[str, str]]:
    """Return the key directory and the headers that sign it for ``host``."""
    components = {'"@authority";req': host.lower()}
    headers = _signed(key, components, "http-message-signatures-directory", created)
    return json.dumps({"keys": [public_jwk(key)]}), headers
