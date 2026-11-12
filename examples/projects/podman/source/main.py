"""Hello world on the standard library alone, run in a container Podman built from a Containerfile.

The output is fixed, so an experiment can verify it exactly and a reviewer's
rerun prints the same bytes.
"""

import hashlib
import platform

GREETING = "Hello, World!"


def main() -> None:
    print("--- Podman Hello World ---")
    print(GREETING)
    print(f"sha256: {hashlib.sha256(GREETING.encode()).hexdigest()}")
    print(f"python: {platform.python_version()}")


if __name__ == "__main__":
    main()
