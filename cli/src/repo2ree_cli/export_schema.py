from __future__ import annotations

import json

from repo2ree_cli.cli import EXIT_CODES, cli
from repo2ree_cli.schema import describe
from repo2ree_core.domain.ree.steps import REE_STEPS


def schema_document() -> str:
    return json.dumps(describe(cli, (), EXIT_CODES, REE_STEPS), indent=2, ensure_ascii=False) + "\n"
