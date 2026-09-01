"""Export the generated OpenAPI document to the committed contract file.

The committed ``contracts/openapi.json`` is the automation-client contract,
frozen as a reviewable artifact: the FastAPI app is one *implementation* of it,
and a replacement backend must serve the same document. It lives in the
top-level ``contracts/`` tree — not in ``api/`` — because the contract is
implementation-neutral; only this generator and the drift test belong to the
implementation. A unit test (``test_openapi_contract``) fails whenever the
app's generated document drifts from the committed file, so every contract
change shows up as a diff of ``contracts/openapi.json`` in review. After an
intentional API change, regenerate:

    just api-openapi        # or: python -m repo2ree_api.export_openapi
"""

from __future__ import annotations

import json
from pathlib import Path

from repo2ree_api.main import app

# <repo root>/contracts/openapi.json — the implementation-neutral contract tree.
CONTRACT_PATH = Path(__file__).resolve().parents[3] / "contracts" / "openapi.json"


def openapi_document() -> str:
    """The generated document in its canonical committed serialization."""
    return json.dumps(app.openapi(), indent=2) + "\n"


def main() -> None:
    CONTRACT_PATH.write_text(openapi_document())
    print(f"wrote {CONTRACT_PATH}")  # noqa: T201 — CLI entrypoint: this is the script's user-facing output


if __name__ == "__main__":
    main()
