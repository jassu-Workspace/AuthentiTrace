import os
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.database.database import engine
from app.database.migrate import upgrade_to_head
from app.api.v1.endpoints import upload, dashboard, reports, jobs, reviews, ops
from app.security import check_startup, rate_limit_general
from app.services.job_runner import recover_jobs
from app.services.media_service import purge_expired_media

DEFAULT_CORS_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]


def get_allowed_origins() -> list[str]:
    """Read comma-separated CORS origins from env, falling back to local development origins."""
    raw_origins = os.getenv("CORS_ALLOW_ORIGINS", "")
    if not raw_origins.strip():
        return DEFAULT_CORS_ORIGINS

    origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
    return origins or DEFAULT_CORS_ORIGINS

@asynccontextmanager
async def lifespan(app: FastAPI):
    check_startup()
    await upgrade_to_head()  # schema is owned by Alembic migrations
    purge_expired_media()
    await recover_jobs()
    yield
    await engine.dispose()

app = FastAPI(
    title="AuthentiTrace API",
    description="Multi-Signal Media Trust Infrastructure powered by a Tamper-Evident Ledger.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Config
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
protected = [Depends(rate_limit_general)]  # API-key check, then the general rate limit
app.include_router(ops.public_router, prefix="/api/v1", tags=["Operations"])
app.include_router(ops.router, prefix="/api/v1/ops", tags=["Operations"], dependencies=protected)
app.include_router(upload.router, prefix="/api/v1/upload", tags=["Upload & Verify"], dependencies=protected)
app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["Background Jobs"], dependencies=protected)
app.include_router(reviews.router, prefix="/api/v1/reviews", tags=["Human Review"], dependencies=protected)
app.include_router(reports.router, prefix="/api/v1/reports", tags=["Explainability Reports"], dependencies=protected)
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Monitoring Dashboard"], dependencies=protected)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
