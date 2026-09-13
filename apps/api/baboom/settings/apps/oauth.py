"""OAuth 2.1 authorization server settings for the MCP endpoint."""

from baboom.settings.base import INSTALLED_APPS
from baboom.settings.env import env

INSTALLED_APPS += ["oauth2_provider"]

MCP_RESOURCE_IDENTIFIER = env(
    "MCP_RESOURCE_IDENTIFIER",
    default="http://localhost:8000/mcp/",
)
OAUTH_ISSUER = env("OAUTH_ISSUER", default="http://localhost:8000/o")

# Approving an authorization means signing in first. Django's default points
# at a route this project does not serve, so it lands on the public site.
LOGIN_URL = "/admin/login/"

# One coarse scope: the token says the holder may reach the endpoint, model
# permissions decide what happens there.
MCP_SCOPE = "mcp:access"

# Tried in order; the first to recognise a request wins. The app that serves
# MCP knows these names and nothing about who issues tokens.
MCP_AUTHENTICATORS = ["baboom.oauth.auth.TokenAuthenticator"]

# Hosts a client may belong to: where its metadata document is served, and
# where an authorization code may be sent. Empty denies every client.
MCP_CLIENT_HOSTS = env.list("MCP_CLIENT_HOSTS", default=[])

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
    "CIMD_ALLOWED_HOSTS": MCP_CLIENT_HOSTS,
    "DCR_ENABLED": True,
    "DCR_REGISTRATION_PERMISSION_CLASSES": (
        "baboom.oauth.registration.RedirectHostAllowlistDCRPermission",
    ),
    "OIDC_ENABLED": True,
    "OIDC_RSA_PRIVATE_KEY": env.str(
        "OIDC_RSA_PRIVATE_KEY",
        default="",
        multiline=True,
    ),
    "OIDC_ISS_ENDPOINT": OAUTH_ISSUER,
    "ACCESS_TOKEN_EXPIRE_SECONDS": 3600,
    "REFRESH_TOKEN_REUSE_PROTECTION": True,
    "ALLOWED_REDIRECT_URI_SCHEMES": ["https"],
    "OAUTH2_PROTECTED_RESOURCE_IDENTIFIER": MCP_RESOURCE_IDENTIFIER,
    "OAUTH2_PROTECTED_RESOURCE_AUTHORIZATION_SERVERS": [OAUTH_ISSUER],
    "OAUTH2_PROTECTED_RESOURCE_NAME": "Baboom catalog MCP",
}
