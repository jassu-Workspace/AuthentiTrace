import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.database.database import engine, Base
from app.api.v1.endpoints import upload, dashboard, reports

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
    # Create DB tables on startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Cleanup logic on shutdowb
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
app.include_router(upload.router, prefix="/api/v1/upload", tags=["Upload & Verify"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["Explainability Reports"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Monitoring Dashboard"])

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
