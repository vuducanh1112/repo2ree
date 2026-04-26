from pathlib import Path

import click

from repo2ree.cli.cli import cli as repo2ree_cli
from repo2ree.core.repo_profiler.repo_profile import (
    profile_repository as _profile_repository,
)


@repo2ree_cli.command()
@click.argument("repo_dir", type=str)
@click.option(
    "output_file",
    "-o",
    type=str,
    default=None,
    help="Output file to save the profile report.",
)
def profile_repository(repo_dir: str, output_file: str | None) -> None:
    """
    Profile a repository and output the report.
    """

    _repo_dir = Path(repo_dir)

    if not _repo_dir.exists():
        raise click.ClickException(f"Repository path {_repo_dir} does not exist.")

    if not _repo_dir.is_dir():
        raise click.ClickException(f"Repository path {_repo_dir} is not a directory.")

    profile = _profile_repository(_repo_dir)
    if output_file:
        output_path = Path(output_file)
        output_path.write_text(profile.model_dump_json(indent=2))
        click.echo(f"Profile report saved to {output_path}")

    click.echo(profile.model_dump_json(indent=2))
