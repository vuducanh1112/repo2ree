from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from scripts.vocabulary.check import check, downstream, edge_problems, mermaid
from scripts.vocabulary.discover import biome_sites, python_sites, typescript_sets, typescript_sites
from scripts.vocabulary.model import Context, Edge, Graph, Ignored, Located, Origin, Reader, Relation, Vocabulary
from scripts.vocabulary.readers import CatalogueTable, ContractSet, RoutedOperations, SourceSet, route_path, words

ROOTS = frozenset({"build", "run", "review_run"})


@dataclass(frozen=True)
class Fixed(Reader):
    names: frozenset[str]

    def describe(self) -> str:
        return "fixed"

    def read(self, context: Context) -> tuple[Located, ...]:
        return (Located("fixed", self.names),)


def context(contracts: dict[str, Any] | None = None, sources: dict[str, Located] | None = None) -> Context:
    spec: Any = SimpleNamespace(operations={"build": "", "run": ""}, review_operations={"review_run": ""})
    return Context(
        load_contract=lambda name: (contracts or {}).get(name, {}),
        load_spec=lambda: spec,
        discover_sources=lambda roots: sources or {},
    )


def vocabulary(name: str, names: set[str]) -> Vocabulary:
    return Vocabulary(name, Origin.SOURCE, Fixed(frozenset(names)), name)


def graph(*vocabularies: Vocabulary, edges: tuple[Edge, ...] = (), **claims: Any) -> Graph:
    roots = (
        Vocabulary("operations", Origin.SPEC, CatalogueTable("operations"), ""),
        Vocabulary("review_operations", Origin.SPEC, CatalogueTable("review_operations"), ""),
    )
    return Graph(("operations", "review_operations"), (*roots, *vocabularies), edges, **claims)


def problems(g: Graph, ctx: Context | None = None) -> list[str]:
    return list(check(g, ctx or context()).problems)


def test_a_vocabulary_that_equals_the_catalogue_holds() -> None:
    assert (
        problems(graph(vocabulary("a", {"build", "run"}), edges=(Edge("a", Relation.EQUALS, ("operations",)),))) == []
    )


def test_an_equal_vocabulary_names_both_what_it_lacks_and_what_no_source_has() -> None:
    edge = Edge("a", Relation.EQUALS, ("operations",))
    assert edge_problems(edge, {"a": frozenset({"build", "bild"}), "operations": frozenset({"build", "run"})}) == [
        "a equals operations: [bild] is in no source",
        "a equals operations: lacks [run]",
    ]


def test_a_vocabulary_within_its_sources_may_lack_names_but_not_add_them() -> None:
    edge = Edge("a", Relation.WITHIN, ("operations",))
    names = {"operations": frozenset({"build", "run"})}
    assert edge_problems(edge, {**names, "a": frozenset({"build"})}) == []
    assert edge_problems(edge, {**names, "a": frozenset({"build", "seal"})}) == [
        "a within operations: [seal] is in no source"
    ]


def test_an_extra_must_be_the_vocabularys_own_and_unused_by_the_sources() -> None:
    edge = Edge("a", Relation.WITHIN, ("operations",), ("build", "metadata", "seal"))
    names = {"operations": frozenset({"build", "run"}), "a": frozenset({"build", "metadata"})}
    assert edge_problems(edge, names) == [
        "a within operations: the extra seal is no name of a",
        "a within operations: the extra build is already in the sources",
    ]


def test_a_derived_edge_is_never_checked() -> None:
    edge = Edge("a", Relation.DERIVED, ("operations",))
    assert edge_problems(edge, {"a": frozenset({"x"}), "operations": frozenset({"build"})}) == []


def test_copies_that_disagree_are_named_with_what_each_has() -> None:
    contracts: dict[str, Any] = {
        "ree": {"$defs": {"A": {"properties": {"build": {}, "run": {}}}}},
        "cli": {"$defs": {"A": {"properties": {"build": {}}}}},
    }
    copied = Vocabulary("a", Origin.CONTRACT, ContractSet(("*:/$defs/A/properties",)), "")
    found = problems(graph(copied, edges=(Edge("a", Relation.WITHIN, ("operations",)),)), context(contracts))
    assert found == [
        "a: its copies disagree: cli:/$defs/A/properties has [] and lacks [run] of ree:/$defs/A/properties"
    ]


def test_a_vocabulary_found_nowhere_or_naming_nothing_is_a_problem() -> None:
    gone = Vocabulary("a", Origin.SOURCE, SourceSet("x.py::GONE"), "")
    assert problems(graph(gone, edges=(Edge("a", Relation.WITHIN, ("operations",)),))) == [
        "a: nothing is found at x.py::GONE"
    ]
    empty = vocabulary("b", set())
    assert "b: fixed names nothing" in problems(graph(empty, edges=(Edge("b", Relation.WITHIN, ("operations",)),)))


def test_a_vocabulary_no_edge_ties_to_a_root_is_unanchored() -> None:
    loose = graph(vocabulary("a", {"build"}), vocabulary("b", {"build"}), edges=(Edge("b", Relation.EQUALS, ("a",)),))
    assert problems(loose) == [
        "a reaches no root: hold it to one, or to a vocabulary that does",
        "b reaches no root: hold it to one, or to a vocabulary that does",
    ]


def test_the_impact_of_a_vocabulary_is_everything_held_to_it() -> None:
    chained = graph(
        vocabulary("a", {"build"}),
        vocabulary("b", {"build"}),
        edges=(Edge("a", Relation.WITHIN, ("operations",)), Edge("b", Relation.EQUALS, ("a",))),
    )
    assert downstream(chained, {"operations"}) == {"operations", "a", "b"}
    assert "operations -->|within| a" in mermaid(chained)


def test_every_set_sharing_a_name_with_the_catalogue_must_be_claimed() -> None:
    contracts = {"protocol": {"$defs": {"Kind": {"enum": ["build", "launch"]}, "Other": {"enum": ["x", "y"]}}}}
    sources = {"core/a.py::STAGES": Located("core/a.py::STAGES", frozenset({"run", "seal"}))}
    found = problems(graph(), context(contracts, sources))
    assert found == [
        "core/a.py::STAGES names [run, seal] and no vocabulary or exception claims it",
        "protocol:/$defs/Kind/enum names [build, launch] and no vocabulary or exception claims it",
    ]
    claimed = graph(ignored=(Ignored("core/a.py::STAGES", "no"), Ignored("protocol:/$defs/Kind/enum", "no")))
    assert problems(claimed, context(contracts, sources)) == []


def test_a_claim_on_nothing_is_stale() -> None:
    stale = graph(ignored=(Ignored("x:/enum", "no"),))
    assert problems(stale) == ["x:/enum is claimed but no set is found there: remove the exception"]


def test_python_sets_are_found_by_where_they_are_bound() -> None:
    source = (
        'Kind = Literal["build", "run"]\n'
        "def evidence():\n"
        '    standing = {name: 1 for name in ("build", "run", "seal")}\n'
        'HINTS = {"build": "a", "run": "b"}\n'
        'OTHER = ("x", "y")\n'
    )
    sites = python_sites("core/a.py", source, ROOTS)
    assert {site: sorted(found.names) for site, found in sites.items()} == {
        "core/a.py::Kind": ["build", "run"],
        "core/a.py::evidence.standing": ["build", "run", "seal"],
        "core/a.py::HINTS": ["build", "run"],
    }


def test_the_guis_sets_are_found_over_its_ast_by_the_declaration_they_sit_in(tmp_path: Path) -> None:
    (tmp_path / "a.ts").write_text(
        'export type Step =\n  | "build"\n  | "run";\n'
        'const KEYS = ["build", "run"] as const;\n'
        'const LABELS = {\n  build: "Build",\n  run: "Run",\n};\n'
        'export const PAGE = {\n  BUILD: "build",\n  RUN: "run",\n} as const;\n'
        "interface Params {\n  build: { strict: boolean };\n  run: Record<string, never>;\n}\n"
        "const PLANS = {\n  build: { go: true },\n  run: { go: false },\n};\n"
        'const SINGLE = ["build"];\n'
        'const OTHER = ["x", "y"];\n'
    )
    sites = typescript_sites(typescript_sets(["a.ts"], root=tmp_path), ROOTS)
    assert sorted(sites) == ["a.ts::KEYS", "a.ts::LABELS", "a.ts::PAGE", "a.ts::PLANS", "a.ts::Params", "a.ts::Step"]
    assert sites["a.ts::Params"].names == frozenset({"build", "run"})
    assert list(biome_sites("gui/biome.json", '"match": "__brand|build|run|(.+)"', ROOTS)) == [
        "gui/biome.json::match.0"
    ]


def test_an_operation_is_spelled_as_words_and_routed_under_the_ree_or_its_review() -> None:
    assert words("review_run_experiment") == ("review", "run-experiment")
    assert route_path("build_experiment_environment") == "/api/v1/rees/{ree_id}/build-experiment-environment"
    assert route_path("review_acquire_source") == "/api/v1/rees/{ree_id}/reviews/acquire-source"
    assert route_path("review_run_experiment") == "/api/v1/rees/{ree_id}/reviews/{review_id}/run-experiment"


def test_a_route_is_posted_only_when_named_after_its_operation_and_placed_at_its_words() -> None:
    openapi = {
        "paths": {
            "/api/v1/rees/{ree_id}/build": {"put": {"operationId": "build", "x-operations": ["build"]}},
            "/api/v1/rees/{ree_id}/run/{name}": {"post": {"operationId": "run", "x-operations": ["run"]}},
            "/api/v1/rees/{ree_id}/upload": {"post": {"operationId": "completeUpload", "x-operations": ["run"]}},
        }
    }
    ctx = context({"openapi": openapi})
    read = {which: RoutedOperations(which).read(ctx)[0].names for which in ("declared", "named", "posted")}
    assert read == {"declared": {"build", "run"}, "named": {"build", "run"}, "posted": {"run"}}
