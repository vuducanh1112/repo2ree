"""Write the command line's contract, ``contracts/cli/cli.schema.json``: what ``ree schema`` prints."""

from __future__ import annotations

import json
from pathlib import Path

from repo2ree_cli.cli import EXIT_CODES, cli
from repo2ree_cli.schema import describe
from repo2ree_core.domain.ree.steps import REE_STEPS

SCHEMA_PATH = Path(__file__).resolve().parents[3] / "contracts" / "cli" / "cli.schema.json"


def schema_document() -> str:
    return json.dumps(describe(cli, (), EXIT_CODES, REE_STEPS), indent=2, ensure_ascii=False) + "\n"


def main() -> None:
    SCHEMA_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCHEMA_PATH.write_text(schema_document(), encoding="utf-8")


if __name__ == "__main__":
    main()
