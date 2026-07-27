"""Tests for shared generated-shell formatting helpers."""

import pytest

from repo2ree_core.authoring.script_generation.shell import assert_no_placeholders


def test_assert_no_placeholders_returns_rendered_text():
    assert assert_no_placeholders("echo ok\n", artifact="x.sh") == "echo ok\n"


def test_assert_no_placeholders_allows_literal_at_markers():
    rendered = "echo 'https://example.test/path@@with@@markers'\n"
    assert assert_no_placeholders(rendered, artifact="x.sh") == rendered


def test_assert_no_placeholders_rejects_unresolved_tokens():
    with pytest.raises(AssertionError, match="unresolved placeholder in generated x.sh"):
        assert_no_placeholders("echo @@MISSING@@\n", artifact="x.sh")
