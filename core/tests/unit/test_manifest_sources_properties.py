"""Property-based checks for the first-party manifest parsers.

The example tests in ``test_manifest_sources.py`` pin each format's mapping;
this file defends what must hold for *every* input:

- totality: no parser raises on arbitrary text (repo content is untrusted);
- the row invariants and the ``merge_locked`` contract, which live as
  postconditions inside the implementation — the properties here mostly
  generate inputs and let those assertions fire;
- generator/parser round-trips for the line-oriented formats, where
  adversarial formatting (whitespace, comments, continuations, extras,
  markers) is exactly what hypothesis is good at.
"""

from __future__ import annotations

import pytest
import yaml
from hypothesis import given
from hypothesis import strategies as st

from repo2ree_core.domain.dependency import Dependency, normalize_package_name
from repo2ree_core.repo_profiler.sources.conda import parse_environment_yml
from repo2ree_core.repo_profiler.sources.manifests import _REGISTRY, merge_locked
from repo2ree_core.repo_profiler.sources.oci import parse_dockerfile
from repo2ree_core.repo_profiler.sources.pypi import parse_requirements_txt, parse_uv_lock

pytestmark = pytest.mark.property

# Sweep the actual scan registry so a newly added ecosystem module is covered
# without touching this file.
_PARSERS = [parser.parse for parser in _REGISTRY]
_PARSER_IDS = [parser.format_id for parser in _REGISTRY]


def _assert_row_invariants(deps: list[Dependency]) -> None:
    for dep in deps:
        assert dep.name
        assert dep.name == normalize_package_name(dep.ecosystem, dep.name)
        assert dep.declared_in is not None or dep.locked_in is not None
        if dep.ecosystem == "oci":
            assert dep.locked_version is None


# --------------------------------------------------------------------------- #
# totality: arbitrary text never raises
# --------------------------------------------------------------------------- #


class TestTotality:
    @given(st.text(max_size=300))
    @pytest.mark.parametrize("parse", _PARSERS, ids=_PARSER_IDS)
    def test_arbitrary_text_never_raises(self, parse, text: str) -> None:
        _assert_row_invariants(parse(text, "some/path"))


# --------------------------------------------------------------------------- #
# merge_locked contract
# --------------------------------------------------------------------------- #

_NAMES = st.sampled_from(["alpha", "beta", "gamma", "delta"])  # small pool forces collisions
_ECOSYSTEMS = st.sampled_from(["pypi", "conda", "npm"])


@st.composite
def _declared_row(draw) -> Dependency:
    return Dependency(
        ecosystem=draw(_ECOSYSTEMS),
        name=draw(_NAMES),
        declared_constraint=draw(st.one_of(st.none(), st.sampled_from(["==1.0", ">=2"]))),
        declared_in="requirements.txt",
    )


@st.composite
def _locked_row(draw) -> Dependency:
    return Dependency(
        ecosystem=draw(_ECOSYSTEMS),
        name=draw(_NAMES),
        direct=False,
        locked_version=draw(st.sampled_from(["1.0.0", "2.3.4"])),
        locked_hashes=draw(st.lists(st.sampled_from(["sha256:a", "sha256:b"]), max_size=2)),
        locked_in="uv.lock",
    )


class TestMergeLocked:
    @given(st.lists(_declared_row(), max_size=6), st.lists(_locked_row(), max_size=6))
    def test_contract_holds_for_every_input(self, declared: list[Dependency], locked: list[Dependency]) -> None:
        # The merge contract is asserted inside merge_locked itself; this test
        # supplies the adversarial inputs and checks what the postconditions
        # leave open: declared rows keep their declared fields, and matched
        # rows gain exactly their lock's resolution.
        merged = merge_locked(declared, locked)
        forks_by_identity: dict[tuple[str, str], list[Dependency]] = {}
        for lock in locked:
            forks_by_identity.setdefault((lock.ecosystem, lock.name), []).append(lock)
        for original, row in zip(declared, merged, strict=False):
            assert row.declared_constraint == original.declared_constraint
            assert row.declared_in == original.declared_in
            assert row.direct is True
            forks = forks_by_identity.get((row.ecosystem, row.name))
            if forks:
                # Duplicate lock entries (marker/platform forks) merge as: first
                # fork's version as representative, union of every fork's hashes.
                assert row.locked_version == forks[0].locked_version
                assert set(row.locked_hashes) == {h for fork in forks for h in fork.locked_hashes}
            else:
                assert row.locked_version == original.locked_version

    @given(st.lists(_declared_row(), max_size=6))
    def test_empty_lock_side_is_identity(self, declared: list[Dependency]) -> None:
        assert merge_locked(declared, []) == declared


# --------------------------------------------------------------------------- #
# generator/parser round-trips
# --------------------------------------------------------------------------- #

_PKG_NAME = st.from_regex(r"[A-Za-z0-9][A-Za-z0-9._-]{0,12}", fullmatch=True)
_CONSTRAINT = st.sampled_from(["==1.2.0", ">=1.0", "~=2.1", "<3", ""])
_PAD = st.sampled_from(["", " ", "  ", "\t"])


@st.composite
def _requirement_line(draw) -> tuple[str, str, str]:
    """(rendered line, expected normalized name, expected constraint)."""
    name = draw(_PKG_NAME)
    constraint = draw(_CONSTRAINT)
    extras = draw(st.sampled_from(["", "[extra]", "[a,b]"]))
    marker = draw(st.sampled_from(["", ' ; python_version > "3.8"']))
    comment = draw(st.sampled_from(["", "  # a comment"]))
    continuation = draw(st.booleans()) and bool(constraint)
    spec = f"{name}{extras}{draw(_PAD)}{'\\\n    ' if continuation else ''}{constraint}"
    return f"{draw(_PAD)}{spec}{marker}{comment}", normalize_package_name("pypi", name), constraint


class TestRoundTrips:
    @given(st.lists(_requirement_line(), max_size=8))
    def test_requirements_txt(self, lines: list[tuple[str, str, str]]) -> None:
        text = "\n".join(line for line, _, _ in lines) + "\n"
        deps = parse_requirements_txt(text, "requirements.txt")
        assert [(d.name, d.declared_constraint or "") for d in deps] == [
            (name, constraint) for _, name, constraint in lines
        ]

    @given(
        st.lists(
            st.tuples(_PKG_NAME, st.sampled_from(["=1.2", "==1.2.0", ">=1.0", ""])),
            max_size=6,
        ),
        st.lists(st.tuples(_PKG_NAME, _CONSTRAINT), max_size=4),
    )
    def test_environment_yml(
        self,
        conda: list[tuple[str, str]],
        pip: list[tuple[str, str]],
    ) -> None:
        conda = [(n, c) for n, c in conda if n.lower() != "python"]
        entries: list[object] = [f"{name}{constraint}" for name, constraint in conda]
        if pip:
            entries.append({"pip": [f"{name}{constraint}" for name, constraint in pip]})
        text = yaml.safe_dump({"name": "env", "dependencies": entries})

        deps = parse_environment_yml(text, "environment.yml")
        expected = [
            ("conda", normalize_package_name("conda", name), constraint or None) for name, constraint in conda
        ] + [("pypi", normalize_package_name("pypi", name), constraint or None) for name, constraint in pip]
        assert [(d.ecosystem, d.name, d.declared_constraint) for d in deps] == expected

    @given(
        st.lists(
            st.tuples(
                st.from_regex(r"[a-z0-9][a-z0-9./-]{0,12}", fullmatch=True),
                st.sampled_from(["", "3.11", "latest"]),
                st.sampled_from(["", "sha256:abc"]),
            ),
            max_size=5,
        )
    )
    def test_dockerfile_from_lines(self, images: list[tuple[str, str, str]]) -> None:
        lines = [
            f"FROM {name}{f':{tag}' if tag else ''}{f'@{digest}' if digest else ''}" for name, tag, digest in images
        ]
        deps = parse_dockerfile("\n".join(lines) + "\n", "Dockerfile")
        expected = [
            (name, tag or None, [digest] if digest else []) for name, tag, digest in images if name != "scratch"
        ]
        assert [(d.name, d.declared_constraint, d.locked_hashes) for d in deps] == expected


# --------------------------------------------------------------------------- #
# metamorphic relations
# --------------------------------------------------------------------------- #

_SEGMENTS = st.lists(st.sampled_from(["foo", "bar", "baz2"]), min_size=1, max_size=3)


@st.composite
def _respelling(draw, segments: list[str]) -> str:
    """One spelling of an identity: same segments, random separators and case."""
    separators = [draw(st.sampled_from(["-", "_", "."])) for _ in segments[1:]]
    word = segments[0] + "".join(s + seg for s, seg in zip(separators, segments[1:], strict=True))
    return "".join(ch.upper() if draw(st.booleans()) else ch for ch in word)


class TestMetamorphic:
    @given(_SEGMENTS, st.data())
    def test_respelling_never_breaks_the_lock_join(self, segments: list[str], data: st.DataObject) -> None:
        """The manifest and the lockfile may spell the same identity
        differently (Foo_Bar vs foo-bar); the merge must join regardless, and
        the result must not depend on which spelling either side used —
        except for the cosmetic name_as_written."""
        spelling_a = data.draw(_respelling(segments))
        spelling_b = data.draw(_respelling(segments))

        def scan(manifest_spelling: str, lock_spelling: str) -> list[Dependency]:
            declared = parse_requirements_txt(f"{manifest_spelling}>=1\n", "requirements.txt")
            lock_text = (
                f'[[package]]\nname = "{lock_spelling}"\nversion = "1.0.0"\n'
                'wheels = [{ url = "u", hash = "sha256:x" }]\n'
            )
            merged = merge_locked(declared, parse_uv_lock(lock_text, "uv.lock"))
            return [row.model_copy(update={"name_as_written": None}) for row in merged]

        first = scan(spelling_a, spelling_b)
        (row,) = first
        assert row.locked_version == "1.0.0"  # the join fired across spellings
        assert row.locked_hashes == ["sha256:x"]
        assert first == scan(spelling_b, spelling_a)

    @given(st.lists(_requirement_line(), max_size=6), st.lists(_requirement_line(), max_size=6))
    def test_requirements_parsing_is_line_local(
        self, a: list[tuple[str, str, str]], b: list[tuple[str, str, str]]
    ) -> None:
        """parse(A + B) == parse(A) + parse(B): requirements.txt lines carry no
        state across lines. (Dockerfiles deliberately violate this — stage
        aliases — see the example suite.)"""
        text_a = "\n".join(line for line, _, _ in a) + "\n"
        text_b = "\n".join(line for line, _, _ in b) + "\n"
        combined = parse_requirements_txt(text_a + text_b, "requirements.txt")
        assert combined == parse_requirements_txt(text_a, "requirements.txt") + parse_requirements_txt(
            text_b, "requirements.txt"
        )

    @given(st.lists(_declared_row(), max_size=5), st.lists(_locked_row(), max_size=5), st.data())
    def test_lock_order_moves_only_the_representative(
        self, declared: list[Dependency], locked: list[Dependency], data: st.DataObject
    ) -> None:
        """Permuting the lock side may change which fork is the representative
        version, but never the joined hash set, lockedness, or identities."""
        shuffled = list(data.draw(st.permutations(locked)))
        first, second = merge_locked(declared, locked), merge_locked(declared, shuffled)
        for row_a, row_b in zip(first[: len(declared)], second[: len(declared)], strict=True):
            assert set(row_a.locked_hashes) == set(row_b.locked_hashes)
            assert (row_a.locked_version is None) == (row_b.locked_version is None)
        assert {(d.ecosystem, d.name) for d in first} == {(d.ecosystem, d.name) for d in second}
