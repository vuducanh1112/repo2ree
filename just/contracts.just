# Regenerate every committed contract: the API and its GUI TypeScript view, the command line, the REE document, the protocol, the behaviour events, and the environment.
[group('Contracts')]
generate-contracts: generate-api-types generate-cli-schema generate-ree-schema generate-protocol-schema generate-behaviour-schema export-config

# Regenerate the committed OpenAPI contract.
[group('Contracts')]
generate-openapi:
    python -m scripts.contracts write openapi

# Regenerate the GUI TypeScript view of the OpenAPI contract.
[group('Contracts')]
generate-api-types: generate-openapi
    python -m scripts.contracts write openapi-types

# Regenerate the committed REE document schema and the REE file tree (contracts/ree/layout.json).
[group('Contracts')]
generate-ree-schema:
    python -m scripts.contracts write ree-schema ree-layout

# Regenerate the committed command-line contract: every `ree` command, its options, stdin and outputs, as `ree schema` prints it.
[group('Contracts')]
generate-cli-schema:
    python -m scripts.contracts write cli-schema

# Regenerate the committed protocol schema: messages, per-operation outputs, and queries.
[group('Contracts')]
generate-protocol-schema:
    python -m scripts.contracts write protocol-schema

# Regenerate the published behaviour event schema (contracts/behaviour) from assurance/spec.
[group('Contracts')]
generate-behaviour-schema:
    python -m scripts.contracts write behaviour-schema

# Require every contract to be what its code renders now, and contracts/ to hold only contracts and fixtures.
[group('Checks')]
check-contracts: _check-write-hint
    python -m scripts.contracts check
