from __future__ import annotations

import argparse
import ast
import io
import re
import subprocess
import sys
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTSIDE = ("docs/", "prototypes/", "presentations/", "examples/", "nix/")
PRAGMA = re.compile(
    r"(noqa(?::\s*[A-Z]+[0-9]+(?:\s*,\s*[A-Z]+[0-9]+)*)?"
    r"|type:\s*ignore(?:\[[^\]]*\])?"
    r"|pragma:\s*no\s*(?:cover|branch)"
    r"|fmt:\s*(?:off|on|skip)"
    r"|ruff:\s*noqa(?::\s*[A-Z0-9, ]+)?"
    r"|isort:\s*skip(?:_file)?)"
)


def _pragmas(comment: str, line: int) -> str | None:
    if line == 1 and comment.startswith("#!"):
        return comment
    if line <= 2 and re.match(r"#.*coding[:=]", comment):
        return comment
    found = [match.group(1).strip() for match in PRAGMA.finditer(comment)]
    return "  ".join(f"# {pragma}" for pragma in found) or None


def _is_string(statement: ast.stmt) -> bool:
    return (
        isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Constant)
        and isinstance(statement.value.value, str)
    )


def stripped(source: str) -> str:
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    dropped: set[int] = set()
    filled: dict[int, str] = {}
    for node in ast.walk(tree):
        for field in ("body", "orelse", "finalbody"):
            body = getattr(node, field, None)
            if not isinstance(body, list) or not body or not isinstance(body[0], ast.stmt):
                continue
            strings = [statement for statement in body if _is_string(statement)]
            emptied = bool(strings) and len(strings) == len(body) and not isinstance(node, ast.Module)
            for statement in strings:
                end = statement.end_lineno or statement.lineno
                dropped.update(range(statement.lineno, end + 1))
                if statement is body[0] and not emptied and end < len(lines) and not lines[end].strip():
                    dropped.add(end + 1)
            if emptied:
                filler = "pass" if isinstance(node, ast.ClassDef) else "..."
                filled[strings[0].lineno] = " " * strings[0].col_offset + filler + "\n"
    comments = {
        token.start[0]: (token.start[1], _pragmas(token.string, token.start[0]))
        for token in tokenize.generate_tokens(io.StringIO(source).readline)
        if token.type == tokenize.COMMENT
    }
    kept: list[str] = []
    for number, line in enumerate(lines, start=1):
        if number in filled:
            kept.append(filled[number])
        elif number in dropped:
            continue
        elif number in comments:
            column, pragmas = comments[number]
            code = line[:column].rstrip()
            ending = "\n" if line.endswith("\n") else ""
            if code:
                kept.append(code + (f"  {pragmas}" if pragmas else "") + ending)
            elif pragmas:
                kept.append(line[:column] + pragmas + ending)
        else:
            kept.append(line)
    return "".join(kept)


def _tracked() -> list[Path]:
    listed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "*.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()
    return [ROOT / name for name in listed if not name.startswith(OUTSIDE) and (ROOT / name).is_file()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/no_comments.py")
    parser.add_argument("--fix", action="store_true")
    parser.add_argument("paths", nargs="*", type=Path)
    args = parser.parse_args(argv)
    commented = []
    for path in args.paths or _tracked():
        source = path.read_text(encoding="utf-8")
        result = stripped(source)
        if result == source:
            continue
        if args.fix:
            path.write_text(result, encoding="utf-8")
        else:
            commented.append(path)
    for path in commented:
        print(f"{path}: comments or docstrings", file=sys.stderr)
    if commented:
        print("python scripts/no_comments.py --fix removes them", file=sys.stderr)
    return 1 if commented else 0


if __name__ == "__main__":
    raise SystemExit(main())
