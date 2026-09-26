from typing import TYPE_CHECKING
from .logger import Logger, setup_logger

if TYPE_CHECKING:
    from .logger import Logger

# Create a default logger instance
logger: Logger = setup_logger("app")

__all__ = ["logger", "setup_logger", "Logger"] 