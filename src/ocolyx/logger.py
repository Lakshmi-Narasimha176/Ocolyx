"""Logging system for Ocolyx."""

from __future__ import annotations

import logging
from logging import Logger
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Optional


LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_WHEN = "midnight"
DEFAULT_LOG_BACKUP_COUNT = 30


def _resolve_log_level(level: str) -> int:
    try:
        return logging.getLevelName(level.upper()) if isinstance(level, str) else int(level)
    except Exception:
        return logging.INFO


def setup_logger(
    log_path: Path,
    log_level: str = DEFAULT_LOG_LEVEL,
    when: str = DEFAULT_LOG_WHEN,
    interval: int = 1,
    backup_count: int = DEFAULT_LOG_BACKUP_COUNT,
) -> Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("ocolyx")
    logger.setLevel(_resolve_log_level(log_level))
    logger.propagate = False

    if logger.handlers:
        logger.handlers.clear()

    formatter = logging.Formatter(LOG_FORMAT)

    file_handler = TimedRotatingFileHandler(
        filename=log_path,
        when=when,
        interval=interval,
        backupCount=backup_count,
        encoding="utf-8",
        utc=True,
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


def get_logger(name: str = "ocolyx") -> Logger:
    return logging.getLogger(name)
