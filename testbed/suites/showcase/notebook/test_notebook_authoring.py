"""A Jupyter notebook run headless over its data: its figure, the data the figure draws, and the executed notebook."""

from __future__ import annotations

import base64
import json
import zipfile

from typed_client import Client, NewRee

from repo2ree_testbed.showcases import NOTEBOOK

F = NOTEBOOK
PNG = b"\x89PNG\r\n\x1a\n"


def test_an_executed_notebook_its_figure_and_its_result_are_sealed(client: Client, new_ree: NewRee) -> None:
    ree_id = new_ree(image=F.image)
    client.author(ree_id, F)

    assert client.seal(ree_id, watch=F.watch).status == "succeeded"
    sealed = zipfile.ZipFile(client.archive(ree_id, "sealed"))
    results = {output: sealed.read(f"ree/results/{F.experiment}/{output}") for output in F.outputs}
    assert b"rate: 0.1735 per hour" in results["result.txt"]
    assert results["figure.png"].startswith(PNG)

    # What the figure shows is kept as data: the table behind it, and each panel as it was drawn.
    curve = results["curve.csv"].decode().splitlines()
    assert (curve[0], len(curve)) == ("hour,measured,fitted", 13)
    panels = json.loads(results["figure.json"])["panels"]
    assert [panel["yscale"] for panel in panels] == ["linear", "log"]
    assert all(len(panel["series"]["measured"]) == 12 for panel in panels)

    cells = [cell for cell in json.loads(results["executed.ipynb"])["cells"] if cell["cell_type"] == "code"]
    assert [cell["execution_count"] for cell in cells] == list(range(1, len(cells) + 1))
    outputs = [output for cell in cells for output in cell["outputs"]]
    printed = "".join(text for output in outputs for text in output.get("text", []))
    assert "half-life: 4.00 hours" in printed
    [shown] = [output["data"]["image/png"] for output in outputs if "image/png" in output.get("data", {})]
    assert base64.b64decode(shown).startswith(PNG)
