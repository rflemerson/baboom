"""Settings for the MCP endpoint."""

# The version this server announces. Raising it is a claim about behaviour,
# so mcp_server holds every response against the matching schema.
#
# 2026-07-28 is published but requires a `resultType` on every result, which
# the library that builds them does not send.
MCP_PROTOCOL_VERSION = "2025-06-18"

DJANGO_ADMIN_MCP_API = {
    "PROTOCOL_VERSION": MCP_PROTOCOL_VERSION,
}
