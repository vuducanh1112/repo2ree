"""Hello world on the standard library alone: nothing to install, nothing to download.

The output is fixed, so an experiment can verify it exactly and a reviewer's
rerun prints the same bytes.
"""

import hashlib

GREETING = "Hello, World!"


def main() -> None:
    print("--- Instant Hello World ---")
    print(GREETING)
    print(f"sha256: {hashlib.sha256(GREETING.encode()).hexdigest()}")


if __name__ == "__main__":
    main()
