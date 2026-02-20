import sys
import hashlib
from loguru import logger
from core.config import settings


def setup_logging():
    logger.remove()
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )
    logger.add(sys.stdout, format=log_format, level="DEBUG" if settings.DEBUG else "INFO", colorize=True)
    logger.add(
        "logs/app.log",
        format=log_format,
        level="INFO",
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        enqueue=True,
    )
    return logger


def anonymize(value: str) -> str:
    """SHA-256 hash for PII anonymization."""
    return hashlib.sha256(value.encode()).hexdigest()[:16]


app_logger = setup_logging()
