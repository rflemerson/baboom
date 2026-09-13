"""OAuth 2.1 authorization server settings for the MCP endpoint."""

from baboom.settings.base import INSTALLED_APPS
from baboom.settings.env import env

INSTALLED_APPS += ["oauth2_provider"]

MCP_RESOURCE_IDENTIFIER = env(
    "MCP_RESOURCE_IDENTIFIER",
    default="http://localhost:8000/mcp/",
)
OAUTH_ISSUER = env("OAUTH_ISSUER", default="http://localhost:8000/o")

# One coarse scope: the token says the holder may reach the endpoint, model
# permissions decide what happens there.
MCP_SCOPE = "mcp:access"

OAUTH2_PROVIDER = {
    "SCOPES": {MCP_SCOPE: "Use the Baboom MCP endpoint"},
    "DEFAULT_SCOPES": [MCP_SCOPE],
    # PKCE_REQUIRED alone still admits the `plain` challenge.
    "COMPLIANT_BCP_RFC9700_PKCE_REQUIRED": True,
    "COMPLIANT_BCP_RFC9700_PKCE_METHOD": True,
    "CIMD_ENABLED": True,
    # The default class accepts a metadata document from any host.
    "CIMD_REGISTRATION_PERMISSION_CLASSES": (
        "oauth2_provider.cimd.HostAllowlistCIMDPermission",
    ),
    "CIMD_ALLOWED_HOSTS": env.list("MCP_CLIENT_HOSTS", default=[]),
    "DCR_ENABLED": True,
    "OIDC_ENABLED": True,
    "OIDC_RSA_PRIVATE_KEY": env("OIDC_RSA_PRIVATE_KEY", default=""),
    "OIDC_ISS_ENDPOINT": OAUTH_ISSUER,
    "ACCESS_TOKEN_EXPIRE_SECONDS": 3600,
    "REFRESH_TOKEN_REUSE_PROTECTION": True,
    "ALLOWED_REDIRECT_URI_SCHEMES": ["https"],
    "OAUTH2_PROTECTED_RESOURCE_IDENTIFIER": MCP_RESOURCE_IDENTIFIER,
    "OAUTH2_PROTECTED_RESOURCE_AUTHORIZATION_SERVERS": [OAUTH_ISSUER],
    "OAUTH2_PROTECTED_RESOURCE_NAME": "Baboom catalog MCP",
}
