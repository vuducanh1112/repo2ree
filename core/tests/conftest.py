"""Give core's property tests their own Hypothesis example database.

The home directory is pinned repo-wide (see the root ``conftest.py``); this
narrows the *example database* — the failing cases Hypothesis replays on the
next run — to ``test-artifacts/property-based-tests/core/``. Entries are keyed
by test identity, so a single shared database would also be correct; the split
is for legibility, and so that dropping one package's accumulated cases never
touches another's.

Loaded at conftest *import* time, deliberately. ``@given`` binds
``settings.default`` when it decorates the test — that is, when the test module
is imported during collection — not when the test runs, so an autouse fixture
would set the profile long after the database for that test was already fixed.
Import time is early enough for exactly one reason: pytest imports a
directory's conftest before the test modules beneath it, so each package's
tests capture their own package's profile even though ``coverage-unit`` runs
every package in a single process and ``settings`` is process-global. A second
package adding property tests gets its own copy of this file; it does not have
to coordinate with this one.
"""

from __future__ import annotations

from hypothesis import settings
from hypothesis.configuration import storage_directory
from hypothesis.database import DirectoryBasedExampleDatabase

_PROFILE = "repo2ree-core"

# intent_to_write=False: this only resolves the path. Asking for a *writable*
# storage directory during conftest import is what Hypothesis's
# side-effect-at-initialization warning exists to catch, and the database
# creates its own directory on first write anyway.
settings.register_profile(
    _PROFILE,
    database=DirectoryBasedExampleDatabase(storage_directory("core", intent_to_write=False).path),
)
settings.load_profile(_PROFILE)
