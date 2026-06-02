from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from repo2ree_core.domain.hbom import HBOM
from repo2ree_core.envelope import GenerateHbomCommand
from repo2ree_core.hbom.generate_hbom import generate_hbom
from repo2ree_api.run_management import (
    _append_run_log,
    _is_cancel_requested,
    _run_summary,
    _start_background_run,
)
from repo2ree_api.storage.workspace_files import (
    WorkspacePatchPayload,
    patch_workspace,
    read_workspace_metadata,
)
from repo2ree_api.workbench.deps import workbench_manager

_log = logging.getLogger(__name__)


# ================================================
# Router
# ================================================


generate_hbom_router = APIRouter()


# ================================================
# Data Models
# ================================================


class CreateGenerateHbomRunPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotencyKey: str | None = None


# ================================================
# Route Handlers
# ================================================


@generate_hbom_router.post("/api/v1/rees/{ree_id}/generate-hbom")
def create_workspace_generate_hbom_run(
    ree_id: str, payload: CreateGenerateHbomRunPayload
):
    run_state = create_generate_hbom_run_state(ree_id, payload)
    return _run_summary(run_state)


# ================================================
# Helpers
# ================================================


def _merge_hbom(existing: HBOM, profiled: HBOM) -> HBOM:
    return HBOM(
        cpus={**profiled.cpus, **existing.cpus},
        gpus={**profiled.gpus, **existing.gpus},
        memory={**profiled.memory, **existing.memory},
        storage={**profiled.storage, **existing.storage},
        network={**profiled.network, **existing.network},
        extra_info={**profiled.extra_info, **existing.extra_info},
    )


def generate_hbom_for_workspace(ree_id: str) -> dict[str, Any]:
    profiled_hbom = generate_hbom()
    current_metadata = read_workspace_metadata(ree_id)
    current_hbom = HBOM.model_validate(
        ((current_metadata.get("reeDraft") or {}).get("hardware_description") or {})
    )
    merged_hbom = _merge_hbom(current_hbom, profiled_hbom)
    patch_workspace(
        ree_id,
        WorkspacePatchPayload(
            reePatch={"hardware_description": merged_hbom.model_dump(exclude_none=True)}
        ),
    )
    return {
        "hardwareDescription": merged_hbom.model_dump(exclude_none=True),
        "componentCounts": {
            "cpus": len(merged_hbom.cpus),
            "gpus": len(merged_hbom.gpus),
            "memory": len(merged_hbom.memory),
            "storage": len(merged_hbom.storage),
            "network": len(merged_hbom.network),
        },
    }


def create_generate_hbom_run_state(
    ree_id: str,
    payload: CreateGenerateHbomRunPayload,
) -> dict[str, Any]:
    request_payload = {"idempotencyKey": payload.idempotencyKey}

    def _runner(ree_id: str, run_id: str) -> tuple[str, dict[str, Any]]:
        _append_run_log(ree_id, run_id, "system", "info", f"Starting hbom run {run_id}")
        if _is_cancel_requested(ree_id, run_id):
            _append_run_log(ree_id, run_id, "system", "warn", "HBOM run canceled")
            return "canceled", {}
        try:
            outputs = generate_hbom_for_workspace(ree_id)
        except Exception as exc:
            _append_run_log(
                ree_id,
                run_id,
                "system",
                "error",
                f"HBOM generation failed: {exc}",
            )
            raise
        _append_run_log(
            ree_id,
            run_id,
            "system",
            "info",
            "Generated hardware description",
        )
        _append_run_log(ree_id, run_id, "system", "info", "HBOM run succeeded")
        _shadow_generate_hbom(ree_id, run_id)
        return "succeeded", outputs

    return _start_background_run(
        ree_id=ree_id,
        operation="hbom",
        request_payload=request_payload,
        run_id_prefix="hbom",
        runner=_runner,
    )


def _shadow_generate_hbom(ree_id: str, run_id: str) -> None:
    handle = workbench_manager.lookup(ree_id)
    if handle is None:
        return
    try:
        result = workbench_manager.dispatch_action(
            handle,
            GenerateHbomCommand(),
            run_id,
            _log.info,  # type: ignore[arg-type]
        )
    except Exception as exc:
        _log.warning("Workbench step generate_hbom failed: %s", exc)
        return
    if result.status != "succeeded":
        _log.warning(
            "Workbench step generate_hbom %s — host-side succeeded", result.status
        )
