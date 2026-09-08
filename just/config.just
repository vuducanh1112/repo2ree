# Generated views and enforcement for the typed environment contract.

[group('Configuration')]
check-config:
    python -m scripts.config.check

[group('Configuration')]
export-config:
    python -m scripts.config.export --write

[group('Configuration')]
show-config owner="all":
    python -m scripts.config.export --show {{ quote(owner) }}
