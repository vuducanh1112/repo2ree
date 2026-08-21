import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import HTTPException as FastAPIHTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from repo2ree_api.authoring.catalog import ree_steps_router, script_templates_router
from repo2ree_api.authoring.definition import definition_router
from repo2ree_api.authoring.evidence import receipts_router
from repo2ree_api.authoring.files import files_router
from repo2ree_api.authoring.inference import inference_router
from repo2ree_api.authoring.seal import seal_router
from repo2ree_api.authoring.source import source_router
from repo2ree_api.authoring.stages import stages_router
from repo2ree_api.contracts import ErrorEnvelope, HealthResponse
from repo2ree_api.control.fleet import agent_ws_router, agents_router, workbench_images_router
from repo2ree_api.control.rees import rees_router
from repo2ree_api.control.run_orchestration import shutdown_runs, startup_runs
from repo2ree_api.control.runs import runs_router
from repo2ree_api.ree_index_routes import ree_index_router
from repo2ree_api.review.records import review_records_router
from repo2ree_api.review.stages import review_stages_router
from repo2ree_api.settings import service_settings
from repo2ree_api.storage.init_storage import create_upload_staging_if_not_exists
from repo2ree_protocol.log import configure_logging, configure_run_log_export
from repo2ree_protocol.tracing import otlp_log_handler, setup_logs, setup_metrics, setup_tracing
from repo2ree_supervisor import WorkbenchUnavailableError

# ================================================
# App Setup
# ================================================


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger_provider = setup_logs("repo2ree-api", endpoint=service_settings.OTLP_ENDPOINT)
    log_handler = otlp_log_handler(logger_provider) if logger_provider is not None else None
    configure_logging(structured=service_settings.OTLP_ENDPOINT is not None, otlp_handler=log_handler)
    # Run-stream lines (workbench LogSink frames landing in the run registry)
    # ship to the collector too, trace-correlated — but never to stdout.
    configure_run_log_export(otlp_log_handler(logger_provider) if logger_provider is not None else None)
    tracer_provider = setup_tracing("repo2ree-api", endpoint=service_settings.OTLP_ENDPOINT, console_fallback=True)
    meter_provider = setup_metrics("repo2ree-api", endpoint=service_settings.OTLP_ENDPOINT)
    create_upload_staging_if_not_exists()
    startup_runs()
    try:
        yield
    finally:
        shutdown_runs()
        if tracer_provider is not None:
            tracer_provider.shutdown()
        if meter_provider is not None:
            meter_provider.shutdown()
        if logger_provider is not None:
            logger_provider.shutdown()


_log = logging.getLogger(__name__)

# The app description lands in the OpenAPI document (`info.description`), so it
# reaches every doc surface at once: Swagger UI (/docs), ReDoc (/redoc), the live
# /openapi.json, and the committed api/openapi.json contract. It documents the
# cross-endpoint *sequencing* that no single operation's docstring can carry —
# per-endpoint payload details stay in the operation schemas.
_DESCRIPTION = """\
Author and execute reusable execution environments (REEs) through connected
runtime agents.

## Authoring lifecycle

Provisioning, uploads, and execution stages are asynchronous: they return a
`run_id`, and clients await completion by long-polling `observeRun` until the
run reaches a terminal status (`succeeded`, `failed`, `canceled`). Definition
and file edits, reads, and sealing are synchronous. A REE is authored end to end
in this order:

1. `createRee` — provision a workbench; await the returned provisioning run.
2. Bring in source, either by reference (`startSourceAcquisition`) or by upload —
   `initializeSourceUpload`, then `uploadSourceBytes` (raw bytes to the returned
   upload URL), then `completeSourceUpload`; await the extraction run.
3. `getReeState` — compact durable state plus file metadata, never inline
   contents; read file bytes via `readReeFile`.
4. Author the workspace: `writeReeFile` / `deleteReeFile`, and record catalog
   metadata via `patchReeDefinition`.
5. Optionally build and assess: `startBuild`, `startActivationTest`,
   `startEvaluate` / `getEvaluateReport`.
6. `sealRee` — freeze the REE; the returned document carries
   `ree.seal.ree_digest`. Download the sealed archive via `downloadReeArchive`.
7. `deleteRee` — tear the workbench down.

A complete, CI-asserted walkthrough of this sequence as real `curl` calls lives
in `api/tests/e2e/api_agent_walkthrough.py` (see the external documentation
link).
"""

_OPENAPI_TAGS = [
    {"name": "rees", "description": "Create, inspect, author, seal, and release REEs."},
    {"name": "runs", "description": "Start and observe asynchronous workbench operations."},
    {"name": "receipts", "description": "Inspect selected, typed author evidence."},
    {"name": "sources", "description": "Acquire, upload, and remove source snapshots."},
    {"name": "files", "description": "Read and mutate files in an REE workspace."},
    {"name": "fleet", "description": "Discover connected runtime agents and workbench images."},
    {"name": "ree-index", "description": "Read the REE index: what was sealed here, and where it was deposited."},
    {"name": "system", "description": "Service health and metadata."},
]

app = FastAPI(
    title="repo2ree Control API",
    version="0.1.0",
    description=_DESCRIPTION,
    openapi_tags=_OPENAPI_TAGS,
    # externalDocs must be an absolute URL — the document is consumed away from
    # the repo (fetched from a live server), so a repo-relative path would
    # dangle. Points at the public Codeberg mirror's walkthrough.
    openapi_external_docs={
        "description": "End-to-end API authoring walkthrough (real curl session, CI-asserted)",
        "url": "https://codeberg.org/vuducanh1112/repo2ree/src/branch/main/api/tests/e2e/README.md",
    },
    lifespan=lifespan,
)
FastAPIInstrumentor.instrument_app(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Registration order is document order in the generated OpenAPI, so it is also
# the reading order a client meets the API in: provision, then the authoring
# lifecycle in step order, then review, then the control plane.
ROUTERS = (
    # Control plane — the REE and its runs exist before any step does.
    rees_router,
    runs_router,
    # Authoring, in the order of repo2ree_core.evidence.step_graph.REE_STEPS.
    ree_steps_router,
    script_templates_router,
    source_router,
    definition_router,
    files_router,
    inference_router,
    stages_router,
    receipts_router,
    seal_router,
    # What sealing leaves behind, once the workbench above is gone.
    ree_index_router,
    # Review — the same lifecycle, reproduced independently.
    review_records_router,
    review_stages_router,
    # The fleet the whole thing runs on.
    workbench_images_router,
    agent_ws_router,
    agents_router,
)

for router in ROUTERS:
    app.include_router(router)


# ================================================
# Exception Handlers
# ================================================


@app.exception_handler(FastAPIHTTPException)
async def http_exception_handler(request: Request, exc: FastAPIHTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict) and "error" in detail:
        content = dict(detail)
        error = dict(content["error"])
        error.setdefault("retryable", exc.status_code in {429, 502, 503, 504})
        content["error"] = error
        return JSONResponse(status_code=exc.status_code, content=content)

    if isinstance(detail, dict):
        error_payload = {
            "code": str(detail.get("code", f"http_{exc.status_code}")),
            "message": str(detail.get("message", detail)),
            "details": detail.get("details"),
            "retryable": bool(detail.get("retryable", False)),
        }
    else:
        error_payload = {
            "code": f"http_{exc.status_code}",
            "message": str(detail),
            "details": None,
            "retryable": exc.status_code in {429, 502, 503, 504},
        }

    return JSONResponse(status_code=exc.status_code, content={"error": error_payload})


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "request_validation_failed",
                "message": "Request validation failed",
                "details": {"violations": exc.errors()},
                "retryable": False,
            }
        },
    )


@app.exception_handler(WorkbenchUnavailableError)
async def workbench_unavailable_handler(request: Request, exc: WorkbenchUnavailableError) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={
            "error": {
                "code": "workbench_unavailable",
                "message": "Workbench unavailable for this REE",
                "details": None,
                "retryable": True,
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    span_context = trace.get_current_span().get_span_context()
    trace_id = f"{span_context.trace_id:032x}" if span_context.is_valid else None
    _log.error("unhandled API exception", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": "An internal error occurred",
                "details": {"trace_id": trace_id} if trace_id else None,
                "retryable": False,
            }
        },
    )


# ================================================
# Routes
# ================================================


@app.get(
    "/",
    tags=["system"],
    operation_id="getHealth",
    response_model=HealthResponse,
    responses={500: {"model": ErrorEnvelope}},
)
def read_root() -> HealthResponse:
    return HealthResponse(status="online", message="This is the REE API backend.")
