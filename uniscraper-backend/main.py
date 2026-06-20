# main.py
# FastAPI application entry point.
# - Creates app with title="UniScraper API", version="1.0.0"
# - Adds CORSMiddleware using settings.cors_origins
# - Registers all four routers under /api/v1 prefix
# - Startup event: calls database.ping(), logs success or failure
# - GET /health returns {"status": "ok", "version": "1.0.0"}
# - Uvicorn runs on host 0.0.0.0, port 8000

# ── Windows Playwright Fix ────────────────────────────────────────────────────
# MUST BE FIRST: Set event loop policy before any other imports.
# Windows uses ProactorEventLoop by default, which doesn't support subprocess
# transports needed by Playwright. SelectorEventLoop fixes this.
import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
# ──────────────────────────────────────────────────────────────────────────────

import logging
from contextlib import asynccontextmanager

# Reconfigure stdout/stderr to UTF-8 to prevent encoding crashes on Windows
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
import database
# Router imports can pull in heavy pipeline modules (Playwright, pdfplumber, etc.)
# which may not be installed in a lightweight dev environment. Import routers
# lazily below and register them only if available so the health endpoint can
# run without all native deps.

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    ok = await database.ping()
    if ok:
        logger.info("[OK] MongoDB connected")
    else:
        logger.warning("[ERROR] MongoDB unavailable - check MONGODB_URI in .env")
    yield
    # Shutdown (nothing to clean up for now)


app = FastAPI(
    title="UniScraper API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Try to import and mount routers. If any import fails (missing optional deps),
# log a warning and continue — the health endpoint will still work.
try:
    import importlib

    scrape = importlib.import_module("routers.scrape")
    history = importlib.import_module("routers.history")
    batch = importlib.import_module("routers.batch")
    export = importlib.import_module("routers.export")

    app.include_router(scrape.router, prefix="/api/v1")
    app.include_router(history.router, prefix="/api/v1")
    app.include_router(batch.router, prefix="/api/v1")
    app.include_router(export.router, prefix="/api/v1")
except Exception as e:
    logger.warning("Some routers failed to import; running in limited mode: %s", e)


@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
