from __future__ import annotations

from pathlib import Path, PurePosixPath

import pytest
from hypothesis import given
from hypothesis import strategies as st

from repo2ree_ree.paths import resolve_within, validate_relative_path

pytestmark = pytest.mark.property

_BASE = Path("/srv/workspace-root")

_SAFE_SEG = st.sampled_from(["a", "b", "sub", "x.y", ".hidden", "."])
_SAFE_REL = st.lists(_SAFE_SEG, min_size=1, max_size=5).map("/".join)

_SEGMENT = st.sampled_from(["a", "b", "sub", "..", ".", "", "x.y", ".hidden"])
_PATHY = st.one_of(
    st.lists(_SEGMENT, min_size=0, max_size=6).map("/".join),
    st.text(alphabet="ab/.\\ ", max_size=10),
)


class TestResolveWithinContainment:
    @given(_PATHY)
    def test_never_escapes_base(self, rel: str) -> None:
        resolved = resolve_within(_BASE, rel)
        if resolved is not None:
            resolved.relative_to(_BASE.resolve())

    @given(_PATHY)
    def test_accepts_iff_lexically_valid(self, rel: str) -> None:
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
        validate_relative_path(rel)
