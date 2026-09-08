# Regenerate the committed API contract and its GUI TypeScript view.
[group('Contracts')]
generate-contracts: generate-api-types

# Regenerate the committed OpenAPI contract.
[group('Contracts')]
generate-openapi:
    python -m repo2ree_api.export_openapi

# Regenerate the GUI TypeScript view of the OpenAPI contract.
[group('Contracts')]
generate-api-types: generate-openapi
    npm --prefix gui run api:types
