"""A figure and the table behind it are results: the author's criterion checks what the figure is, not its bytes."""

from __future__ import annotations

import zipfile

from typed_client import Client, NewRee

from repo2ree_testbed.showcases import PLOTTING

F = PLOTTING
PNG = b"\x89PNG\r\n\x1a\n"


def test_a_figure_and_its_table_are_sealed_beside_the_summary(client: Client, new_ree: NewRee) -> None:
    ree_id = new_ree(image=F.image)
    client.author(ree_id, F)

    assert client.seal(ree_id, watch=F.watch).status == "succeeded"
    sealed = zipfile.ZipFile(client.archive(ree_id, "sealed"))
    results = {output: sealed.read(f"ree/results/{F.experiment}/{output}") for output in F.outputs}
    assert results["figure.png"].startswith(PNG)
    assert results["fit.csv"].decode().splitlines()[0] == "hour,measured,fitted"
    assert b"slope: 1.9909" in results["result.txt"]
