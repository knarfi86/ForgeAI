"""Application-wide logging configuration."""

import logging
from pathlib import Path


def configure_logging(log_path: Path) -> None:
    """Configure the ForgeAI log exactly once for the current process."""
    logger = logging.getLogger("forgeai")
    if logger.handlers:
        return
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
