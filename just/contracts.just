# Regenerate the committed OpenAPI contract.
[group('Contracts')]
api-openapi:
    python -m repo2ree_api.export_openapi

# Regenerate the GUI TypeScript view of the OpenAPI contract.
[group('Contracts')]
api-types:
    npm --prefix gui run api:types
