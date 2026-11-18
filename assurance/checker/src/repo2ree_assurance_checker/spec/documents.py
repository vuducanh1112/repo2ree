"""Document rules: what one commit's document and the files it holds must say of each other.

Each rule reads one capture commit alone, its committed document and the files it holds, and the checker
computes every digest itself: nothing an owner concluded is an input, only something to compare with.
``standing`` holds what core recorded of each receipt to the standing the receipt's basis gives; ``digest``
holds a recorded digest to the checker's own digest of what it names.
"""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from repo2ree_assurance_checker.spec.aggregates import DocumentPath
from repo2ree_assurance_checker.spec.base import Name, SpecModel

type DigestKind = Literal["file", "paths", "canonical", "inventory"]
# A path in the committed tree, relative to the document's root; ``{slug}`` is the judged item's slug.
type TreePath = Annotated[str, Field(pattern=r"^[A-Za-z0-9_.{}/-]*$")]


class FilePair(SpecModel):
    """A recorded digest, and the file it is the digest of: named by a field, or by its path."""

    digest: DocumentPath
    size: DocumentPath | None = None
    file: DocumentPath | None = None  # A field holding the file's path, under ``root``.
    path: TreePath | None = None
    root: TreePath = ""

    @model_validator(mode="after")
    def names_one_file(self) -> Self:
        if (self.file is None) == (self.path is None):
            raise ValueError(f"{self.digest}: a file pair names its file by a field or by a path, not both")
        return self


class PathsPair(SpecModel):
    """A recorded digest over the paths a field declares, read under ``root``."""

    digest: DocumentPath
    paths: DocumentPath
    root: TreePath


class CanonicalPair(SpecModel):
    """A recorded digest of a part of the document, in its canonical encoding under a domain."""

    digest: DocumentPath
    part: DocumentPath
    domain: str = Field(min_length=1)


class DocumentRule(SpecModel):
    id: Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]*$")]
    pattern: Literal["standing", "digest"]
    summary: str
    kind: DigestKind | None = None
    # Only sealed documents (true), only drafts (false), or every one (absent).
    sealed: bool | None = None
    # What a file the commit does not hold means: a violation, or nothing the commit can evidence.
    absent: Literal["violated", "unevidenced"] = "violated"
    pairs: tuple[FilePair, ...] | tuple[PathsPair, ...] | tuple[CanonicalPair, ...] = ()
    # The document's list of the files it carries, each with its path, digest, and size.
    inventory: DocumentPath | None = None
    excepted: tuple[TreePath, ...] = Field(default=(), alias="except")

    @model_validator(mode="after")
    def coherent_rule(self) -> Self:
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
    """The document rules of one aggregate."""

    aggregate: Name
    rules: tuple[DocumentRule, ...] = Field(default=(), alias="rule")

    @model_validator(mode="after")
    def unique_rules(self) -> Self:
        if len({rule.id for rule in self.rules}) != len(self.rules):
            raise ValueError(f"{self.aggregate}: document rule ids must be unique")
        return self
