"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.core.config import settings
from backend.app.core.database import create_connection, init_database
from backend.app.routes import analytics, auth, educational_vision, processing, results, users, videos
from backend.app.services.auth_service import bootstrap_seed_account_passwords


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_database()

    connection = create_connection()
    try:
        bootstrap_seed_account_passwords(connection)
    finally:
        connection.close()

    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Backend API for ThinkNote AI educational video summarization.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(videos.router)
app.include_router(processing.router)
app.include_router(results.router)
app.include_router(analytics.router)
app.include_router(educational_vision.router)
app.mount("/storage", StaticFiles(directory=str(settings.database_path.parent / "backend" / "storage")), name="storage")


@app.get("/", tags=["System"])
def root():
    return {
        "app": settings.app_name,
        "environment": settings.app_env,
        "status": "running",
    }


@app.get("/health", tags=["System"])
def health_check():
    return {"status": "healthy"}
