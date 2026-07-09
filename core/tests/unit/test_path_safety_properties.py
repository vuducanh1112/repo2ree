"""Property-based checks for the workspace path guards.

The containment guarantee in ``resolve_within`` is a "no input should ever
escape" invariant, so it is exercised generatively rather than with a handful
of hand-picked traversals. These properties also drive the module's rejection
branches (absolute, ``..``, wrong-type) that example tests leave uncovered.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

import pytest
from hypothesis import given
from hypothesis import strategies as st

from repo2ree_core.path_safety import (
    normalize_workspace_path,
    resolve_within,
    validate_relative_path,
)

pytestmark = pytest.mark.property

# A fixed base: resolve_within is pure (Path.resolve needs no on-disk path when
# there are no symlinks), so a non-existent root keeps the properties
# deterministic and fixture-free.
_BASE = Path("/srv/workspace-root")

# Safe segments never introduce ``..``, an empty part, or a slash — so a path
# built only from these is lexically valid, and one that also mixes in ``..`` is
# rejected *only* by the parent-traversal branch.
_SAFE_SEG = st.sampled_from(["a", "b", "sub", "x.y", ".hidden", "."])
_SAFE_REL = st.lists(_SAFE_SEG, min_size=1, max_size=5).map("/".join)

# Arbitrary path-ish text: ordinary segments freely mixed with the dangerous
# tokens the guards exist to reject (``..``, leading slashes, empty).
_SEGMENT = st.sampled_from(["a", "b", "sub", "..", ".", "", "x.y", ".hidden"])
_PATHY = st.one_of(
    st.lists(_SEGMENT, min_size=0, max_size=6).map("/".join),
    st.text(alphabet="ab/.\\ ", max_size=10),
)


class TestResolveWithinContainment:
    @given(_PATHY)
    def test_never_escapes_base(self, rel: str) -> None:
        """For any input, the result is None or provably inside base."""
        resolved = resolve_within(_BASE, rel)
        if resolved is not None:
            # .relative_to raises if the resolved path escaped the base.
            resolved.relative_to(_BASE.resolve())

    @given(_PATHY)
    def test_accepts_iff_lexically_valid(self, rel: str) -> None:
        """With no symlinks present, resolve_within succeeds exactly when the
        lexical guard accepts — the two layers agree on plain paths."""
        try:
            validate_relative_path(rel)
        except (TypeError, ValueError):
            lexically_ok = False
        else:
            lexically_ok = True
        assert (resolve_within(_BASE, rel) is not None) == lexically_ok


class TestValidateRelativePath:
    @given(st.lists(_SAFE_SEG, min_size=1, max_size=6).map(lambda p: [*p, ".."]).map("/".join))
    def test_rejects_any_parent_traversal(self, rel: str) -> None:
        with pytest.raises(ValueError, match="'\\.\\.'"):
            validate_relative_path(rel)

    @given(st.one_of(st.integers(), st.none(), st.lists(st.text())))
    def test_rejects_non_path_types(self, value: object) -> None:
        with pytest.raises(TypeError):
            validate_relative_path(value)  # type: ignore[arg-type]

    @given(st.builds(PurePosixPath, _SAFE_REL))
    def test_accepts_purposixpath_of_safe_segments(self, rel: PurePosixPath) -> None:
        validate_relative_path(rel)  # does not raise


class TestNormalizeWorkspacePath:
    @given(st.one_of(st.none(), st.text(max_size=20)))
    def test_idempotent_and_never_absolute(self, value: str | None) -> None:
        once = normalize_workspace_path(value)
        assert normalize_workspace_path(once) == once
        assert not once.startswith("/")
