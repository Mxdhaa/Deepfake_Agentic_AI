"""
Structured JSON Logging
────────────────────────
Uses `structlog` for machine-readable, request-correlated logs.
In development: pretty console output.
In production: JSON lines to stdout (Vercel / cloud log aggregators).
"""

import logging
import sys
import os
import structlog
from typing import Any


def setup_logging() -> None:
    """
    Configure structlog + stdlib logging.
    Call once at application startup.
    """
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    is_dev = os.getenv("ENVIRONMENT", "development") == "development"

    if is_dev:
        # Pretty console output for local dev
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    else:
        # JSON lines for production
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(log_level)


def get_logger(name: str) -> Any:
    """Return a bound structlog logger for the given module name."""
    return structlog.get_logger(name)
