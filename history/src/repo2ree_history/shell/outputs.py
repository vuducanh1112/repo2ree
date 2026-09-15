"""Write fully rendered outputs atomically per file."""

from collections.abc import Mapping
from pathlib import Path
from tempfile import NamedTemporaryFile

from repo2ree_history.core.evidence import AssemblyResult
from repo2ree_history.core.report import render_outputs
from repo2ree_history.shell.files import contained


def write_files(output: Path, files: Mapping[str, str]) -> None:
    # Validate every destination before writing any file.
    destinations = [(contained(output, name), text) for name, text in files.items()]
    for path, text in destinations:
        path.parent.mkdir(parents=True, exist_ok=True)
        pending: Path | None = None
        try:
            with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as temporary:
                pending = Path(temporary.name)
                temporary.write(text)
            pending.replace(path)
        finally:
            if pending is not None:
                pending.unlink(missing_ok=True)


def write_outputs(result: AssemblyResult, output: Path) -> None:
    files = render_outputs(result)
    write_files(output, files)
