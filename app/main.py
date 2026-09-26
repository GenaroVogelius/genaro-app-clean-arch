import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config.settings import Settings
from app.domain.enums.enums import DatabaseTypes
from app.infrastructure.api.main_routes import MainRoutes
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

# Initialize rate limiter (must be before app creation since it's used in lifespan)
limiter = Limiter(key_func=get_remote_address)

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

main_routes = MainRoutes()
app.include_router(main_routes.router, prefix=settings.API_PREFIX, tags=["api rest"])

app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded,
    lambda request, exc: JSONResponse(
        status_code=429, content={"error": "Rate limit exceeded", "status_code": 429}
    ),
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
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unexpected error: {exc!s}")
    return JSONResponse(
        status_code=500, content={"error": "Internal server error", "status_code": 500}
    )
