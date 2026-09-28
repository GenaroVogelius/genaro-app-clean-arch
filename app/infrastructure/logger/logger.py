import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from app.domain.interfaces.logger import LoggerInterface

# Load environment variables from .env file
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    # dotenv not available, continue without it
    pass


class Logger(LoggerInterface):
    """
    Logger class for logging messages to the console and file.
    """

    def __init__(self, name: str):
        self._logger = logging.getLogger(name)
        # Use environment variable to set log level, default to INFO
        log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
        level = getattr(logging, log_level, logging.INFO)
        self._logger.setLevel(level)

        # Prevent adding handlers multiple times
        if self._logger.handlers:
            return

        # Check if running in a container environment
        is_container = (
            os.path.exists("/.dockerenv")
            or os.environ.get("DOCKER_CONTAINER") == "true"
            or os.environ.get("CONTAINER") == "true"
        )

        # Always add console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_format = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        console_handler.setFormatter(console_format)
        self._logger.addHandler(console_handler)

        # File handler - only add if not in container and logs directory exists
        # or can be created
        if not is_container:
            try:
                # Ensure logs directory exists
                os.makedirs("logs", exist_ok=True)

                file_handler = RotatingFileHandler(
                    "logs/app.log",
                    maxBytes=10485760,
                    backupCount=5,  # 10MB
                )
                file_handler.setLevel(level)
                file_format = logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
                file_handler.setFormatter(file_format)
                self._logger.addHandler(file_handler)
            except (OSError, PermissionError):
                # If we can't create the logs directory or file, just use console
                # logging.
                # This is common in CI environments or read-only filesystems
                pass

    def info(self, message: str) -> None:
        self._logger.info(message)

    def error(self, message: str) -> None:
        self._logger.error(message)

    def warning(self, message: str) -> None:
        self._logger.warning(message)

    def debug(self, message: str) -> None:
        self._logger.debug(message)

    def critical(self, message: str) -> None:
        self._logger.critical(message)


def setup_logger(name: str) -> Logger:
    return Logger(name)
