"""A showcase's final REE: each script matched against what inference proposed in the REE's own history."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from repo2ree_repoview.overview.exports import Showcase, ShowcaseTest
from repo2ree_repoview.overview.pages.showcase_ree import page_showcase_ree
from repo2ree_repoview.overview.showcase_ree import preserved_ree

BUILD = "ree-scripts/build_experiment_environment.sh"
ACTIVATE = "ree-scripts/activate_experiment_environment.sh"
EXPERIMENT = "ree-scripts/experiments/hello.sh"
VERIFY = "ree-scripts/experiments/hello.verify.sh"
PROPOSED_BUILD = "#!/usr/bin/env sh\n# Inference rule: root-pip-requirements-v1\npip install\n"
PROPOSED_ACTIVATE = '#!/usr/bin/env sh\nexec "$@"\n'


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def operation(repo: Path, name: str, args: object = None, outputs: object = None) -> None:
    record = {
        "outcome": "succeeded",
        "record": {"command": {"operation": name, "args": args}, "result": {"status": "succeeded", "outputs": outputs}},
    }
    git(repo, "add", "-A")
    git(repo, "commit", "--allow-empty", "-q", "-m", name, "-m", json.dumps(record))


def candidate(target: str, body: str, rule: str) -> dict[str, object]:
    return {
        "target": {"kind": "k", "path": target},
        "status": "needs_input",
        "application": "confirmation_required",
        "candidates": [
            {
                "candidate_id": f"{rule}:1",
                "body": body,
                "inference_rule": rule,
                "decision_leaf": "leaf",
                "warnings": [{"code": "execution_not_validated", "severity": "info"}],
            }
        ],
    }


def write(repo: Path, path: str, body: str) -> None:
    target = repo / "overlay" / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body)
    operation(repo, "write_file", {"path": path, "content": body})


def sealed_test(tmp_path: Path) -> Path:
    """A test's preserved REE: one script as inferred, one chosen over a proposal, one where inference proposed
    nothing, one never asked about."""
    test = tmp_path / "test"
    repo = test / "dossier/rees/abc/ree"
    repo.mkdir(parents=True)
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "t@t")
    git(repo, "config", "user.name", "t")
    (repo / "ree.json").write_text("{}")
    (repo / "snapshot.tar.gz").write_text("version https://git-lfs.github.com/spec/v1\noid sha256:ff\nsize 4096\n")
    operation(repo, "provision")
    report = {
        "results": [
            candidate(BUILD, PROPOSED_BUILD, "root-pip-requirements-v1"),
            candidate(ACTIVATE, PROPOSED_ACTIVATE, "venv-activate-experiment-environment-v1"),
        ]
    }
    operation(repo, "generate_script_candidates", outputs=report)
    write(repo, BUILD, PROPOSED_BUILD)
    write(repo, ACTIVATE, '#!/usr/bin/env sh\nPATH=/venv/bin:$PATH\nexec "$@"\n')
    write(repo, EXPERIMENT, "python main.py\n")
    nothing = {"target": {"kind": "experiment_verify", "path": VERIFY}, "status": "not_inferred"}
    operation(repo, "generate_script_candidates", outputs={"results": [nothing | {"application": "unavailable"}]})
    write(repo, VERIFY, "grep -q Hello result.txt\n")
    operation(repo, "seal_ree", outputs={"sealed_at": "2026-11-13T00:00:00Z", "ree_digest": "sha256:aa"})
    operation(repo, "run_experiment")
    return test


def test_each_script_says_whether_it_is_what_inference_proposed(tmp_path: Path) -> None:
    ree = preserved_ree(sealed_test(tmp_path), ("missing", "abc"))
    assert ree is not None
    written = {script.path: script.written for script in ree.scripts}
    assert written == {
        f"overlay/{BUILD}": "inferred",
        f"overlay/{ACTIVATE}": "chosen_over",
        f"overlay/{EXPERIMENT}": "not_asked",
        f"overlay/{VERIFY}": "no_candidate",
    }
    edited = next(script for script in ree.scripts if script.written == "chosen_over")
    assert "+PATH=/venv/bin:$PATH" in edited.diff()
    assert ree.sealed is not None
    assert ree.sealed.ree_digest == "sha256:aa"
    assert ree.after_seal == 1
    snapshot = next(entry for entry in ree.files if entry.path == "snapshot.tar.gz")
    assert snapshot.lfs is not None
    assert snapshot.lfs.size == 4096


def test_a_test_that_sealed_nothing_has_no_final_ree(tmp_path: Path) -> None:
    repo = tmp_path / "test/dossier/rees/abc/ree"
    repo.mkdir(parents=True)
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "t@t")
    git(repo, "config", "user.name", "t")
    operation(repo, "provision")
    assert preserved_ree(tmp_path / "test", ("abc",)) is None


def test_the_page_shows_the_final_scripts_and_what_inference_was_asked(tmp_path: Path) -> None:
    ree = preserved_ree(sealed_test(tmp_path), ("abc",))
    test = ShowcaseTest(surface="api", workflow="authoring", file="f.py", tier="showcase-api", run="r", test="f.py::t")
    showcase = Showcase(name="hello", kind="showcase", environment="bare", tests=(test,))
    page = page_showcase_ree(showcase, test, ree)
    assert page.slug == "showcase-ree-hello"
    assert "root-pip-requirements-v1" in page.body
    assert "inference not asked" in page.body
    assert "inference proposed nothing" in page.body
    assert "What inference proposed" in page.body
    # The files as a tree: a folder holding its files, each text file opening to its contents.
    assert '<summary><b>overlay/</b><span class="meta">4 files</span></summary>' in page.body
    assert '<summary>ree.json<span class="meta">2 B · Git</span></summary><pre class="code">{}</pre>' in page.body
    assert '<li>snapshot.tar.gz<span class="meta">4.1 kB · <span class="lfs">LFS</span></span></li>' in page.body
    assert "1 operation(s) followed the seal" in page.body
    assert "no run of its API authoring test" in page_showcase_ree(showcase, None, None).body
