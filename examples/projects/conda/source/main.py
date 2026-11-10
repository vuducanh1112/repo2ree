import sys

import numpy as np


def main() -> None:
    matrix = np.array([[2, 1, 0], [1, 3, 1], [0, 1, 4]], dtype=np.int64)
    vector = np.arange(1, 4, dtype=np.int64)
    print("--- Conda NumPy ---")
    print(f"product: {(matrix @ vector).tolist()}")
    print(f"trace of square: {int(np.trace(matrix @ matrix))}")
    print(f"environment: {sys.prefix}")


if __name__ == "__main__":
    main()
