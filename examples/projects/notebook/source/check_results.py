"""Check what decay.ipynb produced against its input data.

Refits the data in plain Python, without numpy, so a bug in the notebook cannot confirm
itself. Run from the folder holding the notebook's outputs, naming its input:

    python3 check_results.py path/to/decay.csv
"""

from __future__ import annotations

import base64
import csv
import json
import math
import struct
import sys
from collections.abc import Callable
from pathlib import Path

PNG = b"\x89PNG\r\n\x1a\n"
FIGURE_SIZE = (1000, 400)

Data = list[tuple[float, float]]
Model = Callable[[float], float]


def check(condition: bool, failure: str) -> None:
    if not condition:
        sys.exit(f"check failed: {failure}")


def png_size(image: bytes) -> tuple[int, int]:
    check(image[:8] == PNG, "not a PNG")
    width, height = struct.unpack(">II", image[16:24])
    return width, height


def read_data(path: Path) -> Data:
    with path.open(encoding="utf-8") as table:
        return [(float(row["hour"]), float(row["concentration"])) for row in csv.DictReader(table)]


def fit(data: Data) -> tuple[float, float]:
    """Least squares of log concentration over hours: the slope and the intercept."""
    hours = [hour for hour, _ in data]
    logs = [math.log(value) for _, value in data]
    mean_hour, mean_log = sum(hours) / len(data), sum(logs) / len(data)
    covariance = sum((h - mean_hour) * (y - mean_log) for h, y in zip(hours, logs, strict=True))
    slope = covariance / sum((h - mean_hour) ** 2 for h in hours)
    return slope, mean_log - slope * mean_hour


def check_result(slope: float) -> None:
    lines = Path("result.txt").read_text(encoding="utf-8").splitlines()
    claimed = [float(line.split()[1]) for line in lines if line.startswith("rate: ")]
    check(len(claimed) == 1, "result.txt states no rate, or more than one")
    check(abs(claimed[0] + slope) < 0.00005, f"result.txt claims a rate of {claimed[0]}, the data fits {-slope:.4f}")


def check_curve(data: Data, model: Model) -> None:
    with Path("curve.csv").open(encoding="utf-8") as table:
        curve = list(csv.DictReader(table))
    over_hours = [float(row["hour"]) for row in curve] == [hour for hour, _ in data]
    check(over_hours, "curve.csv is not over the measured hours")
    for row, (hour, value) in zip(curve, data, strict=True):
        check(abs(float(row["measured"]) - value) < 0.005, f"curve.csv at hour {hour:g} is not the measurement")
        on_fit = math.isclose(float(row["fitted"]), model(hour), rel_tol=1e-3)
        check(on_fit, f"curve.csv at hour {hour:g} is off the fit")


def check_figure(data: Data, model: Model) -> None:
    """What each panel drew, as figure.json records it, and the rendered figure."""
    panels = json.loads(Path("figure.json").read_text(encoding="utf-8"))["panels"]
    check([panel["yscale"] for panel in panels] == ["linear", "log"], "the panels are not linear, then log")
    for panel in panels:
        check((panel["xlabel"], panel["ylabel"]) == ("hour", "concentration"), "a panel's axes are mislabeled")
        check(set(panel["series"]) == {"measured", "fit"}, f"a panel draws {sorted(panel['series'])}")
        measured = panel["series"]["measured"]
        check(len(measured) == len(data), "a panel leaves out measurements")
        for (x, y), (hour, value) in zip(measured, data, strict=True):
            drawn = abs(x - hour) < 1e-4 and abs(y - value) < 1e-4
            check(drawn, f"a panel plots ({x}, {y}), not ({hour:g}, {value})")
        line = panel["series"]["fit"]
        check(len(line) >= 50, "the fit is drawn too coarsely to be a curve")
        check((line[0][0], line[-1][0]) == (data[0][0], data[-1][0]), "the fit does not span the measurements")
        for x, y in line:
            check(math.isclose(y, model(x), rel_tol=1e-3), f"the fit is drawn through ({x}, {y}), off the model")

    size = png_size(Path("figure.png").read_bytes()[:24])
    check(size == FIGURE_SIZE, f"figure.png is {size[0]}x{size[1]}, not {FIGURE_SIZE[0]}x{FIGURE_SIZE[1]}")


def check_notebook() -> None:
    """The executed notebook ran top to bottom, cleanly, and shows its figure."""
    notebook = json.loads(Path("executed.ipynb").read_text(encoding="utf-8"))
    cells = [cell for cell in notebook["cells"] if cell["cell_type"] == "code"]
    counts = [cell["execution_count"] for cell in cells]
    check(counts == list(range(1, len(cells) + 1)), f"cells ran out of order or not at all: {counts}")
    outputs = [output for cell in cells for output in cell["outputs"]]
    errors = [output for output in outputs if output["output_type"] == "error"]
    check(not errors, f"a cell raised: {errors[0]['ename']}: {errors[0]['evalue']}" if errors else "")
    shown = [output["data"]["image/png"] for output in outputs if "image/png" in output.get("data", {})]
    check(len(shown) == 1, f"the notebook shows {len(shown)} figures, not 1")
    png_size(base64.b64decode(shown[0]))


def main(data_path: Path) -> None:
    data = read_data(data_path)
    slope, intercept = fit(data)

    def model(hour: float) -> float:
        return math.exp(intercept + slope * hour)

    check_result(slope)
    check_curve(data, model)
    check_figure(data, model)
    check_notebook()
    print(f"results check out: rate {-slope:.4f} per hour")  # noqa: T201


if __name__ == "__main__":
    main(Path(sys.argv[1]))
