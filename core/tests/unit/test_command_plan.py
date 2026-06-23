"""The command-plan projection must stay in lockstep with what executors run.

These tests pin :func:`describe_plan` to the canonical argv builders in
``container.run_script`` — the very functions the WorkingEnvironment
implementations execute through. If a builder changes, both the executed command
and its projection change together; if the projection stops calling a builder,
these tests fail.
"""

from __future__ import annotations

from repo2ree_core.container.run_script import (
    CONTAINER_WORKSPACE,
    build_exec_command,
    container_name,
    docker_create_argv,
    docker_load_argv,
    docker_rmi_argv,
    experiment_script_rel,
    format_argv,
    runtime_image_tag,
)
from repo2ree_core.domain.env_entry import (
    ContainerEntry,
    CustomEntry,
    LocalEntry,
    VmEntry,
)
from repo2ree_core.working_environment.command_plan import (
    describe_plan,
    native_exec_argv,
    native_shell_command,
)

_RUN_ID = "RUN_ID"
_WORKSPACE = "WORKSPACE"


def _displays(plan, phase_id: str) -> list[str]:
    phase = next(p for p in plan.phases if p.id == phase_id)
    return [c.display for c in phase.commands]


def test_container_docker_plan_phases_match_builders() -> None:
    plan = describe_plan(ContainerEntry(engine="docker"))
    assert plan.kind == "container(docker)"
    assert [p.id for p in plan.phases] == ["pre", "exec", "post"]

    image = runtime_image_tag(_RUN_ID)
    container = container_name(_RUN_ID)

    # Setup mirrors loaded_runtime_image + DockerWorkingEnvironment.__enter__.
    pre = _displays(plan, "pre")
    assert format_argv(docker_load_argv("docker", "ARTIFACT")) in pre
    assert format_argv(docker_create_argv("docker", container=container, image=image)) in pre

    # Teardown mirrors __exit__ + loaded_runtime_image cleanup.
    post = _displays(plan, "post")
    assert format_argv(docker_rmi_argv("docker", image=image, loaded_ref="LOADED_REF")) in post

    # The exec step is exactly run.run_runnable's command step.
    exec_command = build_exec_command(
        CONTAINER_WORKSPACE / experiment_script_rel(_RUN_ID),
        experiment_script_rel(_RUN_ID),
        echo_label=None,
        working_dir=CONTAINER_WORKSPACE,
    )
    assert _displays(plan, "exec") == [f"docker exec {container} sh -c {_quote(exec_command)}"]


def test_container_podman_plan_uses_podman_binary() -> None:
    plan = describe_plan(ContainerEntry(engine="podman"))
    assert plan.kind == "container(podman)"
    pre = _displays(plan, "pre")
    assert format_argv(docker_load_argv("podman", "ARTIFACT")) in pre


def test_container_apptainer_plan_is_flagged_unimplemented() -> None:
    # Apptainer is not Docker-CLI-compatible; rendering Docker verbs for it would
    # be confidently wrong, so the projection flags it instead of inventing argv.
    plan = describe_plan(ContainerEntry(engine="apptainer"))
    assert plan.kind == "container(apptainer)"
    assert plan.phases == []
    assert plan.note


def test_local_plan_reflects_activate_and_has_no_provisioning() -> None:
    plan = describe_plan(LocalEntry(activate="conda activate env"))
    assert plan.kind == "local"
    assert _displays(plan, "pre") == []
    assert _displays(plan, "post") == []

    script_abs = f"{_WORKSPACE}/{experiment_script_rel(_RUN_ID)}"
    expected = native_shell_command(
        activate="conda activate env",
        working_dir=_WORKSPACE,
        script_abs=script_abs,
    )
    assert _displays(plan, "exec") == [format_argv(native_exec_argv(expected, login_shell=False))]
    assert "conda activate env" in _displays(plan, "exec")[0]


def test_local_plan_omits_activate_when_blank() -> None:
    plan = describe_plan(LocalEntry(activate=""))
    exec_display = _displays(plan, "exec")[0]
    assert "set -e; cd" in exec_display  # activate segment dropped, exactly as executor does


def test_custom_plan_shows_script_path() -> None:
    plan = describe_plan(CustomEntry(enter_script="scripts/my-driver"))
    assert plan.kind == "custom"
    assert plan.note
    assert any("scripts/my-driver" in c.display for phase in plan.phases for c in phase.commands)


def test_vm_has_note_and_no_phases() -> None:
    plan = describe_plan(VmEntry())
    assert plan.phases == []
    assert plan.note


def _quote(text: str) -> str:
    return format_argv([text])
