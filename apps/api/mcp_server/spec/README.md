# Protocol schema

One file per protocol version, copied from the specification repository:

    https://github.com/modelcontextprotocol/modelcontextprotocol
    schema/<version>/schema.json

The tests load the one matching `MCP_PROTOCOL_VERSION` and hold every
response against it. The library that supplies the tools validates the
arguments it receives and never what it returns, which is how an invalid
content block once reached a client.

The content is the published document; the repository's hooks trim the
trailing blank line, so compare it parsed rather than byte for byte.

Raising `MCP_PROTOCOL_VERSION` means adding the schema for that version in
the same commit, and letting the tests say what the claim costs.
