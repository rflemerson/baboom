# Protocol schema

`schema-2024-11-05.json` is the Model Context Protocol schema for the version
this server announces, copied from the specification repository:

    https://github.com/modelcontextprotocol/modelcontextprotocol
    schema/2024-11-05/schema.json

The content is the published document; the repository's hooks trim the
trailing blank line, so compare it parsed rather than byte for byte.

It is here so the tests can hold every response against it. The library that
supplies the tools validates the arguments it receives and never what it
returns, which is how an invalid content block reached a client.

Replacing this file is how the announced version changes: update
`PROTOCOL_VERSION` in the same commit, and let the tests say what broke.
