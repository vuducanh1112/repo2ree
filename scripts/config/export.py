#!/usr/bin/env python3
"""Generate the machine-readable environment contract from runtime schemas."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from repo2ree_api.settings import Settings
from repo2ree_provider_docker.config import ProviderEnvironment
from repo2ree_workbench.config import WorkbenchEnvironment

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "contracts/config/environment.json"

# Variables owned by launchers, deployment adapters, or shared protocol code do
# not belong to one service settings model. They are declared here so they are
# still part of the checked contract rather than an invisible exception list.
NON_SERVICE_ENVIRONMENT: dict[str, tuple[str, str]] = {
    "API_BASE_URL": ("test-client", "workflow"),
    "API_DEMO_CAST": ("just", "workflow"),
    "API_DEMO_TRANSCRIPT": ("just", "workflow"),
    "ARGS": ("just", "workflow"),
    "BASH_SOURCE": ("bash", "external"),
    "COVERAGE_FILE": ("coverage", "external"),
    "COV_REPORT": ("just", "workflow"),
    "DEPLOY_ENV": ("protocol", "runtime"),
    "DOCKERHUB_NAMESPACE": ("publishing", "deployment"),
    "DOCKERHUB_REGISTRY": ("publishing", "deployment"),
    "E2E_API_BASE_URL": ("playwright", "internal"),
    "E2E_BASE_URL": ("playwright", "internal"),
    "FILMSTRIP_CAPTURE": ("just", "workflow"),
    "GHCR_NAMESPACE": ("publishing", "deployment"),
    "GHCR_REGISTRY": ("publishing", "deployment"),
    "GIT_INDEX_FILE": ("git", "external"),
    "GUI_ARGS": ("just", "workflow"),
    "GUI_COLLAPSE": ("just", "workflow"),
    "GUI_CORE_COLLAPSE": ("just", "workflow"),
    "HOSTNAME": ("container-runtime", "external"),
    "IMAGE_ARCHIVE_DIR": ("publishing", "workflow"),
    "IMAGE_CANDIDATE_REV": ("publishing", "deployment"),
    "IMAGE_CANDIDATE_STATE_DIR": ("publishing", "workflow"),
    "IMAGE_TAG": ("publishing", "deployment"),
    "IMAGE_VALIDATION_REGISTRY": ("publishing", "deployment"),
    "JOURNAL_TRACE": ("just", "workflow"),
    "LOG_LEVEL": ("protocol", "runtime"),
    "OTEL_EXPORTER_OTLP_HEADERS": ("opentelemetry", "external"),
    "PATH": ("operating-system", "external"),
    "PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH": ("playwright", "external"),
    "REGISTRIES": ("publishing", "deployment"),
    "REPO2REE_BACKEND_IMAGE": ("compose", "deployment"),
    "REPO2REE_BUILD_REVISION": ("protocol", "build"),
    "REPO2REE_EXEC_BUNDLE": ("provider", "deployment"),
    "REPO2REE_GUI_IMAGE": ("compose", "deployment"),
    "REPO2REE_NETWORK": ("compose", "deployment"),
    "REPO2REE_PROVIDER_CONTAINER": ("compose", "internal"),
    "REPO2REE_PROVIDER_IMAGE": ("compose", "deployment"),
    "REPO2REE_PROVIDER_STATE_VOLUME": ("compose", "deployment"),
    "REPO2REE_RESOURCE_OWNER": ("provider", "internal"),
    "REPO2REE_TOOLS_BIN": ("executor", "internal"),
    "REPO2REE_TOOLS_BUNDLE": ("provider", "deployment"),
    "REPO2REE_WORKBENCH_PATH": ("provider", "deployment"),
    "REPO2REE_WORKBENCH_ROOT": ("core", "internal"),
    "SERVICE_VERSION": ("protocol", "runtime"),
    "STACK_BACKEND_IMAGE": ("image-stack", "internal"),
    "STACK_GUI_IMAGE": ("image-stack", "internal"),
    "STACK_PROVIDER_IMAGE": ("image-stack", "internal"),
    "TRACEPARENT": ("tracing", "internal"),
    "TRACE_RELAY": ("tracing", "internal"),
    "VITE_API_BASE_URL": ("gui", "build"),
    "VITE_BUILD_REVISION": ("gui", "build"),
    "VITE_GITHUB_URL": ("gui", "build"),
}

MODELS = (
    ("api", Settings),
    ("provider", ProviderEnvironment),
    ("workbench", WorkbenchEnvironment),
)


def build_contract() -> dict[str, Any]:
    variables: dict[str, dict[str, Any]] = {}
    schemas: dict[str, dict[str, Any]] = {}
    for owner, model in MODELS:
        schema = model.model_json_schema()
        schemas[owner] = schema
        for name, field_schema in schema.get("properties", {}).items():
            variables[name] = {
                "owner": owner,
                "kind": "runtime",
                "schema": field_schema,
            }
    for name, (owner, kind) in NON_SERVICE_ENVIRONMENT.items():
        variables.setdefault(name, {"owner": owner, "kind": kind, "schema": {"type": "string"}})
    return {
        "version": 1,
        "variables": dict(sorted(variables.items())),
        "serviceSchemas": schemas,
    }


def rendered_contract() -> str:
    return json.dumps(build_contract(), indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--check", action="store_true")
    action.add_argument("--show", choices=("all", "api", "provider", "workbench"))
    args = parser.parse_args()
    rendered = rendered_contract()
    if args.write:
        CONTRACT.parent.mkdir(parents=True, exist_ok=True)
        CONTRACT.write_text(rendered)
        return 0
    if args.check:
        if not CONTRACT.exists() or CONTRACT.read_text() != rendered:
            print("configuration contract is stale; run: just config-export")
            return 1
        return 0
    contract = json.loads(rendered)
    for name, detail in contract["variables"].items():
        if args.show == "all" or detail["owner"] == args.show:
            default = detail["schema"].get("default", "<required>")
            print(f"{name:42} {detail['owner']:12} {detail['kind']:10} default={default}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
