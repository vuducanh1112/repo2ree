# Contract generation targets.

.PHONY: api-openapi api-types

# Regenerates the committed OpenAPI contract (contracts/openapi.json) from the
# app. The api unit tests fail when the app drifts from the committed file, so
# run this after any intentional API change and review the diff.
api-openapi:
	python -m repo2ree_api.export_openapi

# Regenerates the frontend TypeScript view of the committed OpenAPI contract.
api-types:
	npm --prefix frontend run api:types
