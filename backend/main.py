"""PostGrab — FastAPI application entry point."""

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.job_manager import job_manager

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# Path to the built frontend (populated during Docker build or npm run build)
STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown hooks."""
    # Startup
    logger.info("PostGrab starting up...")
    settings.temp_path.mkdir(parents=True, exist_ok=True)
    await job_manager.start_cleanup_loop()
    logger.info("Job cleanup loop started. Temp dir: %s", settings.temp_path)
    logger.info("PostGrab ready on port %d", settings.port)

    yield

    # Shutdown
    logger.info("PostGrab shutting down...")
    await job_manager.stop_cleanup_loop()
    # Shut down the Playwright browser singleton if it was started
    try:
        from app.renderers.playwright_renderer import shutdown_browser
        shutdown_browser()
    except Exception:
        pass
    logger.info("PostGrab shut down cleanly.")


app = FastAPI(
    title="PostGrab",
    description="X (Twitter) post downloader — extract, render, and download posts.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# CORS - allow all origins for public downloader API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Import and register routers ──────────────────────────────────────────────
from app.api.routes import router as api_router  # noqa: E402

app.include_router(api_router, prefix="/api")


# ── Root health check (outside /api prefix, for Render native health checks) ─
@app.get("/health")
async def root_health():
    """Root-level health check for Render / load balancers."""
    return {"status": "ok"}


# ── Serve frontend static files ──────────────────────────────────────────────
# In production, the built Vite app lives in ./static/
# Mount assets sub-directory first for JS/CSS/images
if STATIC_DIR.is_dir():
    assets_dir = STATIC_DIR / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    # Serve other static files (favicon, etc.)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # SPA catch-all: serve index.html for any non-API, non-static route
    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        """Serve the SPA index.html for client-side routing."""
        # Don't intercept API routes
        if full_path.startswith("api"):
            return JSONResponse(status_code=404, content={"error": "Not found"})

        # Try to serve static file first
        file_path = STATIC_DIR / full_path
        if full_path and file_path.is_file():
            return FileResponse(str(file_path))

        # Fall back to index.html for SPA routing
        index = STATIC_DIR / "index.html"
        if index.is_file():
            return FileResponse(str(index))

        return JSONResponse(status_code=404, content={"error": "Not found"})


# ── Global error handler ─────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception: %s %s — %s", request.method, request.url, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "An unexpected error occurred.", "code": "internal_error"},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.debug,
    )
