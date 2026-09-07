# Generated views and enforcement for the typed environment contract.

[group('Configuration')]
config-check:
    python -m scripts.config.check

[group('Configuration')]
config-export:
    python -m scripts.config.export --write

[group('Configuration')]
config-show service="all":
    python -m scripts.config.export --show {{ quote(service) }}
