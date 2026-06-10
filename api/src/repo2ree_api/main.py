import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import HTTPException as FastAPIHTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter, SimpleSpanProcessor

from repo2ree_api.activation_test import activation_test_router
from repo2ree_api.build_runtime import build_runtime_router
from repo2ree_api.evaluate import evaluate_router
from repo2ree_api.experiment_run import experiment_run_router
from repo2ree_api.generate_hbom import generate_hbom_router
from repo2ree_api.generate_sbom import generate_sbom_router
from repo2ree_api.manage_ree import manage_ree_router
from repo2ree_api.review_ree import review_ree_router
from repo2ree_api.runs import runs_router
from repo2ree_api.storage.init_storage import (
    create_review_storage_if_not_exists,
    create_upload_staging_if_not_exists,
)
from repo2ree_protocol.log import configure_logging
from repo2ree_supervisor import WorkbenchUnavailableError

# ================================================
# App Setup
# ================================================


def _setup_tracing() -> None:
    provider = TracerProvider(resource=Resource({"service.name": "repo2ree-api"}))
    endpoint = os.environ.get("OTLP_ENDPOINT")
    if endpoint:
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces")))
    else:
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    _setup_tracing()
    create_upload_staging_if_not_exists()
    create_review_storage_if_not_exists()
    yield
    # This runs ON SHUTDOWN (clean up if needed)


app = FastAPI(title="The REE API backend", lifespan=lifespan)
FastAPIInstrumentor.instrument_app(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(build_runtime_router)
app.include_router(experiment_run_router)
app.include_router(generate_hbom_router)
app.include_router(generate_sbom_router)
app.include_router(activation_test_router)
app.include_router(evaluate_router)
app.include_router(runs_router)
app.include_router(manage_ree_router)
app.include_router(review_ree_router)


# ================================================
# Exception Handlers
# ================================================


@app.exception_handler(FastAPIHTTPException)
async def http_exception_handler(request: Request, exc: FastAPIHTTPException):
    detail = exc.detail
    if isinstance(detail, dict) and "error" in detail:
        return JSONResponse(status_code=exc.status_code, content=detail)

    if isinstance(detail, dict):
        error_payload = {
            "code": str(detail.get("code", f"http_{exc.status_code}")),
            "message": str(detail.get("message", detail)),
            "details": detail.get("details"),
        }
    else:
        error_payload = {
            "code": f"http_{exc.status_code}",
            "message": str(detail),
            "details": None,
        }

    return JSONResponse(status_code=exc.status_code, content={"error": error_payload})


@app.exception_handler(WorkbenchUnavailableError)
async def workbench_unavailable_handler(request: Request, exc: WorkbenchUnavailableError):
    return JSONResponse(
        status_code=503,
        content={
            "error": {
                "code": "workbench_unavailable",
                "message": "Workbench unavailable for this REE",
                "details": None,
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": str(exc),
                "details": None,
            }
        },
    )


# ================================================
# Routes
# ================================================


@app.get("/")
def read_root():
    return {"status": "online", "message": "This is the REE API backend."}
