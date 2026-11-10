import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HOURS = np.arange(10, dtype=float)
MEASURED = np.array([2.1, 3.9, 6.2, 7.8, 10.1, 12.2, 13.8, 16.1, 18.0, 19.9])


def main() -> None:
    slope, intercept = np.polyfit(HOURS, MEASURED, 1)
    fitted = slope * HOURS + intercept

    with open("fit.csv", "w", encoding="utf-8") as table:
        table.write("hour,measured,fitted\n")
        for hour, measured, value in zip(HOURS, MEASURED, fitted, strict=True):
            table.write(f"{hour:.0f},{measured:.1f},{value:.4f}\n")

    figure, axes = plt.subplots(figsize=(8, 6), dpi=100)
    axes.scatter(HOURS, MEASURED, label="measured")
    axes.plot(HOURS, fitted, label=f"fit: {slope:.3f} per hour")
    axes.set_xlabel("hour")
    axes.set_ylabel("concentration")
    axes.legend()
    figure.savefig("figure.png", metadata={"Software": None})

    print(f"slope: {slope:.4f}")
    print(f"intercept: {intercept:.4f}")


if __name__ == "__main__":
    main()
