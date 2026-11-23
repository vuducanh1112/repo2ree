from __future__ import annotations

import sys
from pathlib import Path


def emit(content: str | bytes, output: Path | None) -> None:
    if output is None:
        if isinstance(content, bytes):
            sys.stdout.buffer.write(content)
        else:
            sys.stdout.write(content)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        output.write_bytes(content)
    else:
        output.write_text(content, encoding="utf-8")
    print(f"wrote {output}", file=sys.stderr)
