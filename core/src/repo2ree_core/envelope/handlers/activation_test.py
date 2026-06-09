"""Handler for the activation_test operation.

Runs the activation script directly inside the workbench — no nested Docker
container needed because the workbench IS the isolated execution environment.
"""

from __future__ import annotations

from repo2ree_core.container.run_script import LogSink
from repo2ree_core.envelope.handlers._common import run_workspace_script_handler
from repo2ree_core.working_environment import CancelCheck
from repo2ree_protocol.command import ActivationTestArgs
from repo2ree_protocol.result import ActionResult


def handle_activation_test(
    args: ActivationTestArgs,
    *,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    return run_workspace_script_handler(
        args.activation_script_path,
        operation="activation_test",
        noun="Activation",
        output_key="activationScriptPath",
        run_id=run_id,
        log=log,
        is_canceled=is_canceled,
    )
