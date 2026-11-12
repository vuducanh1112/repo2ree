# Regenerate every committed contract: the API and its GUI TypeScript view, the REE document, the protocol, and the behaviour events.
[group('Contracts')]
generate-contracts: generate-api-types generate-ree-schema generate-protocol-schema generate-behaviour-schema

# Regenerate the committed OpenAPI contract.
[group('Contracts')]
generate-openapi:
    python -m repo2ree_api.export_openapi

# Regenerate the GUI TypeScript view of the OpenAPI contract.
[group('Contracts')]
generate-api-types: generate-openapi
    npm --prefix gui run api:types

# Regenerate the committed REE document schema and the REE file tree (contracts/ree/layout.json).
[group('Contracts')]
generate-ree-schema:
    python -m repo2ree_ree.export_schema

# Regenerate the committed protocol schema: messages, per-operation outputs, and queries.
[group('Contracts')]
generate-protocol-schema:
    python -m repo2ree_protocol.export_schema

# Regenerate the published behaviour event schema (contracts/behaviour) from assurance/spec.
[group('Contracts')]
generate-behaviour-schema:
    python -m repo2ree_assurance_checker generate-schema
