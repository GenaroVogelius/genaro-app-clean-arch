"""
Database initialization module.
This module provides database-agnostic initialization functions.
"""

from app.domain.enums.enums import DatabaseTypes
from app.infrastructure.logger import logger

# Global variable to store the FastAPI app instance
_fastapi_app = None


def set_fastapi_app(app):
    """
    Set the FastAPI app instance for database integration.
    This should be called from the main FastAPI application.
    """
    global _fastapi_app
    _fastapi_app = app


async def initialize_databases(db_types: list[DatabaseTypes]):
    """
    Initialize database connections for the given database types.
    """
    try:
        if DatabaseTypes.MONGODB in db_types:
            from app.infrastructure.db.mongo.database import connect_to_mongo

            await connect_to_mongo()
            logger.info("MongoDB connection established")

    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise


async def close_database_connections(db_types: list[DatabaseTypes]):
    """
    Close database connections for the given database types.
    """
    try:
        if DatabaseTypes.MONGODB in db_types:
            from app.infrastructure.db.mongo.database import close_mongo_connection

            await close_mongo_connection()
            logger.info("MongoDB connection closed")

    except Exception as e:
        logger.error(f"Error closing database connection: {str(e)}")
        raise
