from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import HTTPException as FastAPIHTTPException
from fastapi.requests import Request
from fastapi.responses import JSONResponse

from repo2ree_api.build_runtime import build_runtime_router
from repo2ree_api.generate_hbom import generate_hbom_router
from repo2ree_api.generate_sbom import generate_sbom_router
from repo2ree_api.activation_test import activation_test_router
from repo2ree_api.evaluate import evaluate_router
from repo2ree_api.runs import runs_router
from repo2ree_api.manage_ree import manage_ree_router
from repo2ree_api.review_ree import review_ree_router
from fastapi.middleware.cors import CORSMiddleware
from repo2ree_api.storage.init_storage import (
    create_workspace_storage_if_not_exists,
    create_review_storage_if_not_exists,
)


# ================================================
# App Setup
# ================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    # This runs ON STARTUP
    create_workspace_storage_if_not_exists()
    create_review_storage_if_not_exists()
    yield
    # This runs ON SHUTDOWN (clean up if needed)


app = FastAPI(title="The REE API backend", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(build_runtime_router)
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
