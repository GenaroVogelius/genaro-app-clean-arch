import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config.settings import Settings
from app.domain.common import DatabaseTypes
from app.infrastructure.api.podcast_routes import router as podcast_router
from app.infrastructure.api.rate_limit import build_limiter, setup_rate_limiting
from app.infrastructure.db.main import (
    close_database_connections,
    initialize_databases,
    set_fastapi_app,
)
from app.infrastructure.logger import logger

logging.getLogger("fastapi").setLevel(logging.INFO)
logging.getLogger("uvicorn").setLevel(logging.INFO)
logging.getLogger("uvicorn.access").setLevel(logging.INFO)

settings = Settings()

DATABASE_TYPES = [DatabaseTypes.MONGODB]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        set_fastapi_app(app)
        await initialize_databases(DATABASE_TYPES)

        logger.info("Aplicación iniciada correctamente")
        logger.info("Documentación disponible en: http://localhost:8000/docs")
    except Exception as e:
        logger.error(f"Error en startup: {e!s}")
        raise

    # One HTTP client shared by every outbound adapter, so connections are
    # reused across requests. Closed on shutdown.
    async with httpx.AsyncClient() as http_client:
        app.state.http_client = http_client
        yield

    # Shutdown
    try:
        await close_database_connections(DATABASE_TYPES)
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error during shutdown: {e!s}")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    debug=settings.DEBUG,
    description=settings.DESCRIPTION,
    lifespan=lifespan,
)

app.include_router(podcast_router, prefix=settings.API_PREFIX, tags=["podcasts"])

# Before CORS, so CORS stays the outermost middleware.
setup_rate_limiting(
    app, build_limiter(settings.RATE_LIMIT, settings.RATE_LIMIT_ENABLED)
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.ALLOW_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    logger.error(f"HTTP error {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code},
        headers=exc.headers,
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unexpected error: {exc!s}")
    return JSONResponse(
        status_code=500, content={"error": "Internal server error", "status_code": 500}
    )
