"""The script-template catalog ``ree templates`` prints."""

from __future__ import annotations

from repo2ree_authoring.templates import (
    activate_experiment_environment_templates,
    build_templates,
    experiment_run_templates,
    experiment_verify_templates,
    script_template_catalog,
)
from repo2ree_protocol.catalog import ScriptTemplateEntry
from repo2ree_ree.reserved_paths import (
    RESERVED_ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT,
    RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT,
    RESERVED_EXPERIMENT_SCRIPT_DIR,
)


def _assert_entries_match(entries: list[ScriptTemplateEntry], expected_keys: list[str]) -> None:
    assert [entry.key for entry in entries] == expected_keys
    # The first entry is the default, and the only one.
    assert [entry.is_default for entry in entries] == [index == 0 for index in range(len(entries))]
    for entry in entries:
        assert entry.label
        assert entry.description
        assert entry.body.startswith("#!/usr/bin/env sh")
        assert "set -eu" in entry.body


def test_the_catalog_names_every_script_kind_and_where_it_belongs() -> None:
    catalog = script_template_catalog()

    # Build and activate carry the seeded reserved paths and their named
    # template variants (venv first, the default a fresh REE is seeded with).
    assert catalog.build_experiment_environment.path == RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT
    _assert_entries_match(catalog.build_experiment_environment.templates, [t.key for t in build_templates()])
    assert catalog.build_experiment_environment.templates[0].key == "venv"
    assert catalog.activate_experiment_environment.path == RESERVED_ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT
    _assert_entries_match(
        catalog.activate_experiment_environment.templates,
        [t.key for t in activate_experiment_environment_templates()],
    )
    assert catalog.activate_experiment_environment.templates[0].key == "venv"

    # Each experiment script kind states its path convention and its variants.
    assert catalog.experiment_run.path_pattern == f"{RESERVED_EXPERIMENT_SCRIPT_DIR}/{{slug}}.sh"
    _assert_entries_match(catalog.experiment_run.templates, [t.key for t in experiment_run_templates()])
    assert catalog.experiment_run.templates[0].key == "command"
    assert catalog.experiment_verify.path_pattern == f"{RESERVED_EXPERIMENT_SCRIPT_DIR}/{{slug}}.verify.sh"
    _assert_entries_match(catalog.experiment_verify.templates, [t.key for t in experiment_verify_templates()])


def test_the_default_templates_need_no_container_engine() -> None:
    catalog = script_template_catalog()

    for section in (catalog.build_experiment_environment, catalog.activate_experiment_environment):
        default = section.templates[0]
        assert default.is_default
        assert "docker" not in default.body
