import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1.router import api_router

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown logic.

    Phase 12 (deployment hardening, docs/MASTER_PLAN.md #2.5/#2.4):
    startup used to also run `Base.metadata.create_all`, alongside a real
    Alembic migration history in alembic/versions/ - two schema sources of
    truth for the same database. That was never exercised by the test
    suite either way (tests/conftest.py runs its own create_all against a
    separate in-memory engine, and httpx.ASGITransport in this codebase's
    test client does not invoke lifespan events - see
    tests/test_alembic_migrations.py for the one place a migration
    actually runs). Deployment is now `alembic upgrade head` only (see
    docs/DEPLOYMENT_PLAN.md #9) - a schema change with no matching
    migration will now fail loudly against a real database instead of a
    stray create_all silently patching over it.
    """
    # --- Startup ---
    logger.info("Starting ATLAS Backend (version %s)...", settings.VERSION)
    settings.validate_for_environment()
    yield

    # --- Shutdown ---
    logger.info("Shutting down ATLAS Backend...")
    from app.database.session import engine
    await engine.dispose()
    logger.info("Database connections closed.")


def create_application() -> FastAPI:
    application = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        lifespan=lifespan,
    )

    # Phase 12 / SECURITY_PLAN.md S7: allow_origins=["*"] combined with
    # allow_credentials=True is an invalid combination per the CORS spec
    # (browsers reject it), and wrong regardless for an API whose only
    # client is a native Android app, not a browser - CORS exists to
    # protect browser-mediated requests, so an empty allow-list is correct
    # here, not a placeholder. settings.CORS_ORIGINS stays available for a
    # future browser-based client (e.g. a web UI) to opt in explicitly.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response

    application.include_router(api_router, prefix=settings.API_V1_STR)

    return application


app = create_application()
