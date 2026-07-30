"""Pin Hypothesis's on-disk state to the repo, not to the working directory.

Hypothesis defaults its home directory to ``Path.cwd() / ".hypothesis"``, so the
example database and the generator caches land wherever pytest happened to be
invoked from — this tree had accumulated both ``./.hypothesis`` and
``./core/.hypothesis``, meaning a failing example found by ``make core-tests``
was invisible to a run started from ``core/``. Anchoring the home directory to
the repo root makes the location a property of the repo rather than of the
shell, and puts it under the gitignored artifact root the rest of the suite
already writes to.

Set here rather than via ``hypothesis.configuration.set_hypothesis_home_dir`` so
that conftest collection costs no hypothesis import for the packages that have
no property tests: ``storage_directory()`` reads this variable lazily, on first
use. ``setdefault`` so an explicit override from the environment still wins.

Layout under the home directory:

    test-artifacts/property-based-tests/
        <package>/          per-package example database (see the package's
                            tests/conftest.py — a shared database would work,
                            entries are keyed by test identity, but one
                            directory per package keeps "what has this package
                            found?" answerable with ls)
        constants/          hypothesis's own machine-local caches, created
        unicode_data/       alongside on first use

None of it is committed: durable regressions get pinned as ``@example`` in the
test source, and this directory is a cache — deleting it costs a re-search, not
a test.
"""

from __future__ import annotations

import os
from pathlib import Path

HYPOTHESIS_HOME = Path(__file__).parent / "test-artifacts" / "property-based-tests"

os.environ.setdefault("HYPOTHESIS_STORAGE_DIRECTORY", str(HYPOTHESIS_HOME))
