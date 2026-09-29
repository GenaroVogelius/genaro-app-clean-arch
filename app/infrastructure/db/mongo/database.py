import importlib
import inspect
from pathlib import Path

from beanie import Document, init_beanie
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import ServerSelectionTimeoutError

from app.config.settings import get_settings
from app.infrastructure.logger import logger

settings = get_settings()


class Database:
    client: AsyncMongoClient | None = None
    database: AsyncDatabase | None = None


# Global database instance
db = Database()


def _discover_repository_document_modules() -> list[str]:
    """Build dotted import paths for Beanie documents under
    ``repositories/*_repository/*_document.py``.

    Each subdirectory of ``repositories`` whose name ends with ``_repository``
    is scanned for ``*_document.py`` files; each file becomes
    ``app.infrastructure.db.mongo.repositories.<pkg>.<module>``.

    Returns:
        Sorted module paths so document registration order is stable across runs.
    """
    repos_root = Path(__file__).resolve().parent / "repositories"
    pkg_prefix = "app.infrastructure.db.mongo.repositories"
    modules: list[str] = []
    if not repos_root.is_dir():
        return modules
    for child in sorted(repos_root.iterdir()):
        if not child.is_dir() or not child.name.endswith("_repository"):
            continue
        for document_file in sorted(child.glob("*_document.py")):
            modules.append(f"{pkg_prefix}.{child.name}.{document_file.stem}")
    return modules


def get_document_models() -> list[type[Document]]:
    """
    Automatically discover all Document models defined in the repository
    document modules.
    Returns a list of all classes that inherit from Document.
    """
    document_models: list[type[Document]] = []

    for module_path in _discover_repository_document_modules():
        module = importlib.import_module(module_path)
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(obj, Document)
                and obj is not Document
                and obj.__module__ == module.__name__
            ):
                document_models.append(obj)

    return document_models


async def connect_to_mongo():
    """Create database connection"""
    try:
        db.client = AsyncMongoClient(
            settings.MONGODB_URL,
            serverSelectionTimeoutMS=5000,  # 5 second timeout
            connectTimeoutMS=5000,
            socketTimeoutMS=5000,
            tz_aware=True,  # return UTC-aware datetimes, matching the domain models
        )

        # Test the connection
        await db.client.admin.command("ping")
        logger.info(f"Connected to MongoDB at {settings.MONGODB_HOST}")

        db.database = db.client[settings.MONGODB_DATABASE]

        # Initialize Beanie with document models (automatically discovered)
        await init_beanie(database=db.database, document_models=get_document_models())

        logger.info(f"Beanie initialized for database: {settings.MONGODB_DATABASE}")

    except ServerSelectionTimeoutError:
        logger.error("Failed to connect to MongoDB: Server selection timeout")
        raise
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise


async def close_mongo_connection():
    """Close database connection"""
    if db.client:
        await db.client.close()
        db.client = None
        db.database = None


async def get_database():
    """Get database instance"""
    if db.database is None:
        await connect_to_mongo()
    return db.database


async def get_client():
    """Get MongoDB client instance"""
    if db.client is None:
        await connect_to_mongo()
    return db.client


async def check_mongo_health() -> bool:
    """Check if MongoDB connection is healthy"""
    try:
        if db.client is None:
            return False
        await db.client.admin.command("ping")
        return True
    except Exception:
        return False
