"""A Monte Carlo estimate of pi on the standard library: each run draws its own seed and prints a different result.

The seed is printed so one run can be replayed; the claim is the estimate, within a tolerance.
"""

import random
import secrets

SAMPLES = 200_000


def main() -> None:
    seed = secrets.randbits(64)
    rng = random.Random(seed)  # noqa: S311
    inside = sum(rng.random() ** 2 + rng.random() ** 2 <= 1 for _ in range(SAMPLES))
    print(f"seed: {seed}")
    print(f"pi estimate: {4 * inside / SAMPLES:.6f}")


if __name__ == "__main__":
    main()
