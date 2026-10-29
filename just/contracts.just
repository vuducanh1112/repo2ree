# Regenerate the committed API contract and its GUI TypeScript view.
[group('Contracts')]
generate-contracts: generate-api-types generate-ree-schema generate-protocol-schema

# Regenerate the committed OpenAPI contract.
[group('Contracts')]
generate-openapi:
    python -m repo2ree_api.export_openapi

# Regenerate the GUI TypeScript view of the OpenAPI contract.
[group('Contracts')]
generate-api-types: generate-openapi
    npm --prefix gui run api:types

# Regenerate the committed REE document schema.
[group('Contracts')]
generate-ree-schema:
    python -m repo2ree_ree.export_schema

# Regenerate the committed protocol schema: messages, per-operation outputs, and queries.
[group('Contracts')]
generate-protocol-schema:
    python -m repo2ree_protocol.export_schema
