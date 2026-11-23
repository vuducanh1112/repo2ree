from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from repo2ree_assurance_checker.spec.aggregates import DocumentPath
from repo2ree_assurance_checker.spec.base import Name, SpecModel

SIGNATURE_SUFFIX = ".sigstore.json"

type DigestKind = Literal["file", "paths", "canonical", "inventory"]
type TreePath = Annotated[str, Field(pattern=r"^[A-Za-z0-9_.{}/-]*$")]


class FilePair(SpecModel):
    digest: DocumentPath
    size: DocumentPath | None = None
    file: DocumentPath | None = None
    path: TreePath | None = None
    root: TreePath = ""

    @model_validator(mode="after")
    def names_one_file(self) -> Self:
        if (self.file is None) == (self.path is None):
            raise ValueError(f"{self.digest}: a file pair names its file by a field or by a path, not both")
        return self


class PathsPair(SpecModel):
    digest: DocumentPath
    paths: DocumentPath
    root: TreePath


class CanonicalPair(SpecModel):
    digest: DocumentPath
    part: DocumentPath
    domain: str = Field(min_length=1)


class ReferencePair(SpecModel):
    field: DocumentPath
    ree: DocumentPath


class AgreesPair(SpecModel):
    field: DocumentPath
    same: DocumentPath


type VerdictPolicy = Literal["swhid", "sbom-closure", "activation", "verify-script", "after-activation"]


class DocumentRule(SpecModel):
    id: Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]*$")]
    pattern: Literal["standing", "digest", "signature", "reference", "agrees", "verdict"]
    summary: str
    kind: DigestKind | None = None
    sealed: bool | None = None
    absent: Literal["violated", "unevidenced"] = "violated"
    pairs: (
        tuple[FilePair, ...]
        | tuple[PathsPair, ...]
        | tuple[CanonicalPair, ...]
        | tuple[ReferencePair, ...]
        | tuple[AgreesPair, ...]
    ) = ()
    policies: tuple[VerdictPolicy, ...] = ()
    inventory: DocumentPath | None = None
    excepted: tuple[TreePath, ...] = Field(default=(), alias="except")
    files: TreePath | None = None
    subject: DocumentPath | None = None
    claims: dict[Name, Annotated[str, Field(min_length=1)]] = Field(default_factory=dict)

    def excepts(self, path: str) -> bool:
        return any(
            path == excepted or (excepted.endswith("/") and path.startswith(excepted)) for excepted in self.excepted
        )

    @model_validator(mode="after")
    def coherent_rule(self) -> Self:
        if self.pattern in {"reference", "agrees"}:
            taken: type[ReferencePair | AgreesPair] = ReferencePair if self.pattern == "reference" else AgreesPair
            if self.kind or not self.pairs or not all(isinstance(pair, taken) for pair in self.pairs):
                raise ValueError(f"{self.id}: a {self.pattern} rule takes {taken.__name__}s, and no kind")
            return self
        if self.pattern == "verdict":
            if not self.policies or self.kind or self.pairs:
                raise ValueError(f"{self.id}: a verdict rule names its ladders, and no pairs")
            return self
        if self.policies:
            raise ValueError(f"{self.id}: only a verdict rule names ladders")
        signing = (self.files, self.subject, self.claims)
        if self.pattern == "signature":
            if not all(signing) or self.kind or self.pairs or self.inventory:
                raise ValueError(f"{self.id}: a signature rule names its files, the subject they sign, and the claims")
            if not (self.files or "").endswith("/"):
                raise ValueError(f"{self.id}: a signature rule's files are a directory, ending in /")
            return self
        if any(signing):
            raise ValueError(f"{self.id}: only a signature rule names signature files, a subject, or claims")
        if self.pattern == "standing":
            if self.kind or self.pairs or self.inventory:
                raise ValueError(f"{self.id}: a standing rule reads the receipts' basis, and names nothing more")
            return self
        if self.kind is None:
            raise ValueError(f"{self.id}: a digest rule says what kind of digest it computes")
        if self.kind == "inventory":
            if self.inventory is None or self.pairs:
                raise ValueError(f"{self.id}: an inventory rule names the inventory, and no pairs")
            return self
        expected = {"file": FilePair, "paths": PathsPair, "canonical": CanonicalPair}[self.kind]
        if not self.pairs or not all(isinstance(pair, expected) for pair in self.pairs):
            raise ValueError(f"{self.id}: a {self.kind} rule takes {expected.__name__}s")
        return self


class DocumentRules(SpecModel):
    aggregate: Name
    document: Name | None = None
    reviews: DocumentPath | None = None
    rules: tuple[DocumentRule, ...] = Field(default=(), alias="rule")

    @property
    def name(self) -> str:
        return self.document or self.aggregate

    @model_validator(mode="after")
    def unique_rules(self) -> Self:
        if len({rule.id for rule in self.rules}) != len(self.rules):
            raise ValueError(f"{self.name}: document rule ids must be unique")
        if (self.document is None) != (self.reviews is None):
            raise ValueError(f"{self.name}: a review names its document and the field naming the reviewed seal")
        reviewing = {"reference", "agrees", "verdict"}
        if self.reviews is None and (found := [rule.id for rule in self.rules if rule.pattern in reviewing]):
            raise ValueError(f"{found[0]}: only a review's rules reference, agree, or settle verdicts")
        return self
