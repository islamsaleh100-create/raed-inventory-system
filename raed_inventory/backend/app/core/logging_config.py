"""
Structured logging configuration for Raed Inventory System.

Environments:
- local:             human-readable, DEBUG level, colorized where supported
- staging/production: JSON structured, INFO level, machine-parseable

Usage:
    from app.core.logging_config import setup_logging
    setup_logging()          # call once at app startup
"""

import logging
import logging.config
import sys
import time
from typing import Any

# ---------------------------------------------------------------------------
# Optional: pythonjsonlogger for JSON output. Gracefully degrade if absent.
# ---------------------------------------------------------------------------
try:
    from pythonjsonlogger import jsonlogger  # type: ignore
    _JSON_LOGGER_AVAILABLE = True
except ImportError:
    _JSON_LOGGER_AVAILABLE = False


# ---------------------------------------------------------------------------
# JSON formatter (production / staging)
# ---------------------------------------------------------------------------

class _JsonFormatter(logging.Formatter):
    """
    Minimal JSON log formatter that does NOT require pythonjsonlogger.
    Emits one JSON object per line.  Fields:
        timestamp, level, logger, message, [exc_info]
    """

    def format(self, record: logging.LogRecord) -> str:
        import json

        log_obj: dict[str, Any] = {
            "timestamp": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Extra fields injected via logger.info("...", extra={"request_id": ...})
        _SKIP = {
            "name", "msg", "args", "created", "filename", "funcName",
            "levelname", "levelno", "lineno", "module", "msecs",
            "pathname", "process", "processName", "relativeCreated",
            "thread", "threadName", "stack_info", "exc_info", "exc_text",
            "message",
        }
        for key, value in record.__dict__.items():
            if key not in _SKIP and not key.startswith("_"):
                log_obj[key] = value

        if record.exc_info:
            log_obj["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(log_obj, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# Human-readable formatter (local development)
# ---------------------------------------------------------------------------

class _HumanFormatter(logging.Formatter):
    """
    Coloured, human-readable formatter for local development.
    Falls back to plain text when the terminal does not support ANSI colours.
    """

    _COLOURS = {
        "DEBUG":    "\033[36m",   # cyan
        "INFO":     "\033[32m",   # green
        "WARNING":  "\033[33m",   # yellow
        "ERROR":    "\033[31m",   # red
        "CRITICAL": "\033[35m",   # magenta
    }
    _RESET = "\033[0m"

    _FMT = "{colour}[{level:<8}]{reset} {time} | {name} | {message}"

    def __init__(self, use_colour: bool = True):
        super().__init__()
        self._use_colour = use_colour and sys.stderr.isatty()

    def format(self, record: logging.LogRecord) -> str:
        colour = self._COLOURS.get(record.levelname, "") if self._use_colour else ""
        reset  = self._RESET if self._use_colour else ""
        ts     = self.formatTime(record, datefmt="%H:%M:%S")

        line = self._FMT.format(
            colour=colour,
            level=record.levelname,
            reset=reset,
            time=ts,
            name=record.name,
            message=record.getMessage(),
        )

        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)

        return line


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def setup_logging(environment: str | None = None) -> None:
    """
    Configure root logger and all package loggers.

    Parameters
    ----------
    environment:
        One of "local", "staging", "production".
        Defaults to the value read from ``app.config.settings``.
    """
    if environment is None:
        from app.config import settings
        environment = settings.ENVIRONMENT

    is_local = environment == "local"

    level      = logging.DEBUG if is_local else logging.INFO
    formatter  = _HumanFormatter() if is_local else _JsonFormatter()
    handler    = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Attach the request_id filter so every log line can reference the current request.
    # (Filter is imported lazily to avoid circular imports at bootstrap.)
    try:
        from app.core.request_context import RequestIdLogFilter
        handler.addFilter(RequestIdLogFilter())
    except Exception:  # pragma: no cover — defensive; never block logging init
        pass

    # Silence noisy third-party loggers
    _QUIET = {
        "uvicorn.access":    logging.WARNING,
        "sqlalchemy.engine": logging.WARNING,
        "sqlalchemy.pool":   logging.WARNING,
        "passlib":           logging.WARNING,
        "httpx":             logging.WARNING,
    }

    root = logging.getLogger()
    root.setLevel(level)

    # Remove any handlers already attached (e.g. basicConfig defaults)
    root.handlers.clear()
    root.addHandler(handler)

    for logger_name, logger_level in _QUIET.items():
        logging.getLogger(logger_name).setLevel(logger_level)

    # Uvicorn's own error logger should stay visible
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)

    logging.getLogger(__name__).debug(
        "Logging initialised",
        extra={"environment": environment, "level": logging.getLevelName(level)},
    )
