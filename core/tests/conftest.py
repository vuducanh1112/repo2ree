from __future__ import annotations

from hypothesis import settings
from hypothesis.configuration import storage_directory
from hypothesis.database import DirectoryBasedExampleDatabase

_PROFILE = "repo2ree-core"

settings.register_profile(
    _PROFILE,
    database=DirectoryBasedExampleDatabase(storage_directory("core", intent_to_write=False).path),
)
settings.load_profile(_PROFILE)
