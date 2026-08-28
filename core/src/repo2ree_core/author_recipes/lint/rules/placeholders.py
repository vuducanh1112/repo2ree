"""Report unedited template placeholders and command scaffolds."""

from __future__ import annotations

from typing import ClassVar

from repo2ree_core.author_recipes.lint.catalog import make_finding
from repo2ree_core.author_recipes.lint.models import Finding, ScriptContext
from repo2ree_protocol.command import TargetKind

PLACEHOLDER = "EDIT-ME"


class UneditedPlaceholderRule:
    code = "unedited_placeholder"
    codes: ClassVar[frozenset[str]] = frozenset({"unedited_placeholder"})
    applies_to: ClassVar[frozenset[TargetKind]] = frozenset(
        {"build", "activation_run", "activation_verify", "experiment_run", "experiment_verify"}
    )

    def check(self, context: ScriptContext) -> tuple[Finding, ...]:
        # Placeholders are meaningful inside quoted values, so inspect source rather than tokens.
        return tuple(
            make_finding(self.code, path=context.path, line=number, detail=line.strip())
            for number, line in enumerate(context.source.splitlines(), start=1)
            if PLACEHOLDER in line
        )


class EmptyCommandScaffoldRule:
    code = "empty_command_scaffold"
    codes: ClassVar[frozenset[str]] = frozenset({"empty_command_scaffold"})
    applies_to: ClassVar[frozenset[TargetKind]] = frozenset({"activation_run", "experiment_run"})

    def check(self, context: ScriptContext) -> tuple[Finding, ...]:
        # Tokenization excludes the commented examples rendered above the live scaffold.
        words = context.words.words
        findings = []
        for index, word in enumerate(words):
            if word.text != "set":
                continue
            rest = [w for w in words[index + 1 :] if w.line == word.line]
            if [w.text for w in rest] == ["--"]:
                findings.append(make_finding(self.code, path=context.path, line=word.line))
        return tuple(findings)
