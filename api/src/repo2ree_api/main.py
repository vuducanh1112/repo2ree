import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from starlette.exceptions import HTTPException

from repo2ree_api.authoring.catalog import ree_steps_router, script_templates_router
from repo2ree_api.authoring.definition import definition_router
from repo2ree_api.authoring.evidence import receipts_router
from repo2ree_api.authoring.files import files_router
from repo2ree_api.authoring.history import history_router
from repo2ree_api.authoring.inference import inference_router
from repo2ree_api.authoring.lint import lint_router
from repo2ree_api.authoring.seal import seal_router
from repo2ree_api.authoring.source import source_router
from repo2ree_api.authoring.stages import stages_router
from repo2ree_api.contracts import ErrorEnvelope, HealthResponse
from repo2ree_api.control.behaviour import behaviour_router
from repo2ree_api.control.fleet import (
    workbench_ws_router,
    workbenches_router,
)
from repo2ree_api.control.rees import rees_router
from repo2ree_api.control.run_orchestration import shutdown_runs, startup_runs, stop_runs
from repo2ree_api.control.runs import runs_router
from repo2ree_api.deps import workbench_connections
from repo2ree_api.ree_index_routes import ree_index_router
from repo2ree_api.review.records import review_records_router
from repo2ree_api.review.stages import review_stages_router
from repo2ree_api.settings import service_settings
from repo2ree_api.storage import author_actions
from repo2ree_api.storage.init_storage import create_upload_staging_if_not_exists
from repo2ree_protocol.build import BuildInfo, current_build
from repo2ree_supervisor import ReeBusyError, WorkbenchUnavailableError
from repo2ree_telemetry.behaviour import close_journal, open_journal
from repo2ree_telemetry.bootstrap import otlp_log_handler, setup_logs, setup_metrics, setup_tracing
from repo2ree_telemetry.log import configure_logging, configure_run_log_export

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
    # Opened before startup settles interrupted runs, so those transitions are
    # journaled too; closed only after the worker pool has drained.
    open_journal(service_settings.BEHAVIOUR_JOURNAL_DIR, "api", hosts=("api", "supervisor"))
    startup_runs()
    try:
        yield
    finally:
        # Following stops, and workbenches still connected lose their connection with the control
        # plane, which ends every follow: the commands run on for the next API process.
        stop_runs()
        workbench_connections.close_all("shutdown")
        shutdown_runs()
        # The workers drained, so what is still open was never answered (an upload the author never
        # completed), or is left to the next process. The former fails here, before the journal closes.
        final = service_settings.BEHAVIOUR_FINAL_SHUTDOWN
        author_actions.settle_open("abandoned", final=final)
        close_journal(final=final)
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
workbench services.

## Authoring lifecycle

Creating an REE, source extraction, every execution stage, and sealing are
asynchronous: they return a `run_id`. `observeRun` waits until there are new log
entries or the run ends, so it can return while the run is still `running`: call
it again with `next_cursor` until `run.status` is terminal (`succeeded`, `failed`,
`canceled`). Definition and file edits, reads, and generating script candidates
are synchronous. A REE is authored end to end in this order:

1. Discover: `listStores` says what each store's workbench offers (`backend`,
   `images`, `capabilities`). `listReeSteps` gives the steps, their prerequisites,
   and the operations that advance each. `listScriptTemplates` gives the starter
   scripts and where they belong.
2. `createRee` — create the REE in a store; await the returned run. It declares the
   image you ask for or the store's first, or the store's host if it offers none,
   and starts with scripts that suit that environment.
3. Bring in source, either by reference (`startSourceAcquisition`) or by upload —
   `initializeSourceUpload`, then `uploadSourceBytes` (raw bytes to the returned
   `upload_url`, relative to this API), then `completeSourceUpload`; await the
   extraction run.
4. `getReeState` — compact durable state plus file metadata, never inline contents;
   read file bytes via `readReeFile`. Its `audit` says what is still missing and why.
5. Build: `generateScriptCandidates` proposes a build script from the project.
   `writeReeFile` writes it, `patchReeDefinition` declares its
   `build_runtime.runtime_path`, then `startBuild`.
6. `generateScriptCandidates` also scaffolds the activation script, then
   `startActivationTest`. The scaffolds refuse to run until you fill in the command.
7. Declare each experiment via `patchReeDefinition`, write its run and verify
   scripts as in step 6, then `startExperiment`.
8. Optionally assess: `startEvaluate` / `getEvaluateReport`, `startSbomGeneration`,
   `startSbomCrossCheck`, and record catalog metadata via `patchReeDefinition`.
9. `sealRee` — freeze the REE; await the returned run, after which `getRee` carries
   `ree.seal.ree_digest`. Download the sealed archive via `downloadReeArchive`.
10. `deleteRee` — delete the REE from its store.

The external documentation link is a walkthrough of this sequence as real `curl`
calls.
"""

_OPENAPI_TAGS = [
    {"name": "rees", "description": "Create, inspect, author, seal, and release REEs."},
    {"name": "runs", "description": "Start and observe asynchronous workbench operations."},
    {"name": "receipts", "description": "Inspect selected, typed author evidence."},
    {"name": "sources", "description": "Acquire, upload, and remove source snapshots."},
    {"name": "files", "description": "Read and mutate files in an REE workspace."},
    {"name": "fleet", "description": "Discover connected workbench services and workbench images."},
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
    # dangle. Points at the walkthrough script on the public Codeberg mirror.
    openapi_external_docs={
        "description": "End-to-end API authoring walkthrough (real curl session)",
        "url": "https://codeberg.org/vuducanh1112/repo2ree/src/branch/main/testbed/suites/walkthrough/api_walkthrough.py",
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
    # Authoring, in the order of repo2ree_authoring.steps.REE_STEPS.
    ree_steps_router,
    script_templates_router,
    source_router,
    definition_router,
    files_router,
    inference_router,
    lint_router,
    stages_router,
    receipts_router,
    seal_router,
    history_router,
    # What sealing leaves behind, once the workbench above is gone.
    ree_index_router,
    # Review — the same lifecycle, reproduced independently.
    review_records_router,
    review_stages_router,
    # The fleet the whole thing runs on.
    workbench_ws_router,
    workbenches_router,
    # What the fleet's owners recorded, for checking it against the behaviour specification.
    behaviour_router,
)

for router in ROUTERS:
    app.include_router(router)


@app.get(
    "/api/v1/system/build-info",
    response_model=BuildInfo,
    operation_id="getBuildInfo",
    tags=["system"],
)
def get_build_info() -> BuildInfo:
    return current_build("repo2ree-api")


# ================================================
# Exception Handlers
# ================================================


# Starlette's, not only FastAPI's subclass: routing (404, 405) and body parsing (400) raise Starlette's.
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
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


def _is_json(content_type: str) -> bool:
    media_type = content_type.split(";", 1)[0].strip().lower()
    return media_type in {"", "application/json"} or media_type.endswith("+json")


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    # A body the route reads as JSON, sent as something else: FastAPI hands it on as raw bytes, which
    # fail validation, but the request is wrong in its media type, not in its fields.
    if not _is_json(request.headers.get("content-type", "")) and any(error["loc"][:1] == ("body",) for error in errors):
        return JSONResponse(
            status_code=415,
            content={
                "error": {
                    "code": "unsupported_media_type",
                    "message": "The request body must be application/json",
                    "details": None,
                    "retryable": False,
                }
            },
        )
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "request_validation_failed",
                "message": "Request validation failed",
                # The inputs the violations quote can be anything a client sent, bytes included.
                "details": {"violations": jsonable_encoder(errors)},
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


@app.exception_handler(ReeBusyError)
async def ree_busy_handler(request: Request, exc: ReeBusyError) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={
            "error": {
                "code": "ree_busy",
                "message": "Another command runs in this REE; try again once it ended",
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
    return HealthResponse(status="online", message="This is the REE API backend. It describes itself at /openapi.json.")
