#!/usr/bin/env python3
"""Render the walkthrough's asciinema .cast into a standalone markdown transcript.

A .cast plays back well but is a poor standalone document — you can't skim,
search, or link into a recording. This derives the written form from the *same*
artifact: the recording's output stream is text, so the transcript is the
recording, not a separately-maintained (and drift-prone) description. Chapters
are recovered from the walkthrough's own section banners, author asides
(``# ...`` notes) become prose, assertions (``✓``) become bold lines, and the
real commands with their real responses stay as fenced console blocks.

Stdlib-only, like the walkthrough itself:

    render_cast_transcript.py <in.cast> <out.md>
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# CSI sequences (colors, styles) and OSC sequences (titles) — everything the
# walkthrough emits for the terminal but a markdown reader must not see.
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")

# The walkthrough's chapter banner after ANSI stripping: `━━ <title> ━━━...`.
_CHAPTER = re.compile(r"^━━ (.*?) ?━*$")


def cast_output(path: Path) -> str:
    """Concatenate a .cast v2 file's output events into plain text."""
    lines = path.read_text().splitlines()
    chunks: list[str] = []
    for line in lines[1:]:  # first line is the header object
        if not line.strip():
            continue
        event = json.loads(line)
        if event[1] == "o":
            chunks.append(event[2])
    text = "".join(chunks).replace("\r\n", "\n").replace("\r", "\n")
    return _ANSI.sub("", text)


def render(text: str, source_name: str) -> str:
    """Chapter-split the transcript text into a markdown document."""
    out: list[str] = []
    code: list[str] = []

    def flush_code() -> None:
        if code:
            # Trim blank edges so fences hug the content.
            while code and not code[0].strip():
                code.pop(0)
            while code and not code[-1].strip():
                code.pop()
        if code:
            out.append("```text")
            out.extend(code)
            out.append("```")
            out.append("")
            code.clear()

    seen_title = False
    for raw in text.split("\n"):
        line = raw.rstrip()
        banner = _CHAPTER.match(line)
        if banner:
            flush_code()
            out.append(f"## {banner.group(1)}")
            out.append("")
        elif line.lstrip().startswith("# "):
            # An author aside — prose, not terminal output.
            flush_code()
            out.append(line.lstrip()[2:])
            out.append("")
        elif line.lstrip().startswith(("✓ ", "✗ ")):
            flush_code()
            out.append(f"**{line.strip()}**")
            out.append("")
        elif not seen_title and line.strip():
            # The first non-empty line is the session title.
            out.append(f"# {line.strip()}")
            out.append("")
            out.append(
                f"*Written form of the recorded terminal session (`{source_name}`) — "
                "generated from the recording itself, every command and response is "
                "the real one.*"
            )
            out.append("")
            seen_title = True
        elif line or code:
            code.append(raw)
    flush_code()
    return "\n".join(out).rstrip() + "\n"


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(f"usage: {argv[0]} <in.cast> <out.md>", file=sys.stderr)
        return 2
    cast, dest = Path(argv[1]), Path(argv[2])
    dest.write_text(render(cast_output(cast), cast.name))
    print(f"wrote {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
