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
from repo2ree_api.review.signing import review_signing_router
from repo2ree_api.review.stages import review_stages_router
from repo2ree_api.settings import service_settings
from repo2ree_api.storage import author_actions
from repo2ree_api.storage.init_storage import create_upload_staging_if_not_exists
from repo2ree_protocol.build import BuildInfo, current_build
from repo2ree_supervisor import ReeBusyError, WorkbenchUnavailableError
from repo2ree_telemetry.behaviour import close_journal, open_journal
from repo2ree_telemetry.bootstrap import otlp_log_handler, setup_logs, setup_metrics, setup_tracing
from repo2ree_telemetry.log import configure_logging, configure_run_log_export


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger_provider = setup_logs("repo2ree-api", endpoint=service_settings.OTLP_ENDPOINT)
    log_handler = otlp_log_handler(logger_provider) if logger_provider is not None else None
    configure_logging(structured=service_settings.OTLP_ENDPOINT is not None, otlp_handler=log_handler)
    configure_run_log_export(otlp_log_handler(logger_provider) if logger_provider is not None else None)
    tracer_provider = setup_tracing("repo2ree-api", endpoint=service_settings.OTLP_ENDPOINT, console_fallback=True)
    meter_provider = setup_metrics("repo2ree-api", endpoint=service_settings.OTLP_ENDPOINT)
    create_upload_staging_if_not_exists()
    open_journal(service_settings.BEHAVIOUR_JOURNAL_DIR, "api", hosts=("api", "supervisor"))
    startup_runs()
    try:
        yield
    finally:
        stop_runs()
        workbench_connections.close_all("shutdown")
        shutdown_runs()
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

1. Discover: `listStores` says which machine each store's workbench runs an REE's
   scripts on (`machine`). `listReeSteps` gives the steps, their prerequisites,
   where the REE stands on each and which is next, and the operations that
   advance each. `listScriptTemplates` gives the starter
   scripts and where they belong.
2. `createRee` — create the REE in a store; await the returned run. It starts with
   every script it has: starter build and activate scripts, a launch that runs each
   script directly, and a check of the working environment that passes as it comes.
   `writeScript` overwrites a script; none is ever deleted.
3. Bring in source, either by reference (`acquireSource`) or by upload —
   `initializeSourceUpload`, then `uploadSourceBytes` (raw bytes to the returned
   `upload_url`, relative to this API), then `completeSourceUpload`; await the
   extraction run.
4. `getReeState` — compact durable state plus file metadata, never inline contents;
   read file bytes via `readReeFile`. Its `audit` says what is still missing and why.
5. Build: `suggestScripts` proposes a build script from the project.
   `writeScript` writes it, `patchReeDefinition` declares its
   `build_experiment_environment.experiment_environment_path`, then `buildExperimentEnvironment`.
6. `suggestScripts` also proposes the activate experiment environment script;
   `writeScript` writes it, then `activateExperimentEnvironment` runs it alone, around a command
   that does nothing. Experiments run only while that activation's evidence is current.
7. For each experiment, in this order: `patchReeDefinition` declares it, which
   gives it a starter run script and a verify script that passes; removing or
   renaming it takes its scripts with it. `suggestScripts` with its name
   proposes a run script; `writeScript` writes that and, if the experiment checks
   its result, the verify script; then `runExperiment`.
8. Optionally assess: `evaluateReproducibility` / `getReproducibilityReport`, `generateSbom`,
   `crossCheckSbom`, and record catalog metadata via `patchReeDefinition`.
9. `sealRee` — freeze the REE; await the returned run, after which `getRee` carries
   `ree.seal.ree_digest`. Download the sealed archive via `downloadReeArchive`.
10. `deleteRee` — delete the REE from its store.

To replace a source, `removeSource` keeps the REE's scripts and definition; bring
in the new one as in step 3.

## Reviewing a sealed REE

1. `createRee`, then `initializeReeBundleUpload`, `uploadReeBundleBytes`, and
   `loadReeBundle` with the archive; await the load run.
2. `reviewAcquireSource` opens the review and its run reproduces the source;
   `listReviews` gives its `review_id`.
3. `reviewBuildExperimentEnvironment`, `reviewActivateExperimentEnvironment`, and `reviewRunExperiment` for each
   experiment; await each run. A review's `status` is about the runs so far, so run
   every step you want checked.
4. `getReview` gives each step's verdict and the basis it was reached on: `bundled`
   evidence the archive carries, or an `independent` rebuild.

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
ROUTERS = (
    rees_router,
    runs_router,
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
    ree_index_router,
    review_records_router,
    review_stages_router,
    review_signing_router,
    workbench_ws_router,
    workbenches_router,
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


@app.get(
    "/",
    tags=["system"],
    operation_id="getHealth",
    response_model=HealthResponse,
    responses={500: {"model": ErrorEnvelope}},
)
def read_root() -> HealthResponse:
    return HealthResponse(status="online", message="This is the REE API backend. It describes itself at /openapi.json.")
