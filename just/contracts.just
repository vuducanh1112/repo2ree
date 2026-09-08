# Regenerate the committed OpenAPI contract.
[group('Contracts')]
generate-openapi:
    python -m repo2ree_api.export_openapi

# Regenerate the GUI TypeScript view of the OpenAPI contract.
[group('Contracts')]
generate-api-types:
    npm --prefix gui run api:types
