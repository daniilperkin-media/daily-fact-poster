"""
Centralized logger for Daily Fact Poster.
Writes timestamped output to stdout and a rotating log file in logs/.

Usage:
    from .logger import get_logger
    log = get_logger()
    log.info("Step started")
    log.warning("Something looks off")
    log.error("Step failed", exc_info=True)
"""
import logging
import logging.handlers
import os
import sys

from .paths import REPO_ROOT

_LOGGERS: dict = {}


def get_logger(name: str = "daily_fact") -> logging.Logger:
    """Return (or create) the named logger with console + file handlers."""
    if name in _LOGGERS:
        return _LOGGERS[name]

    log = logging.getLogger(name)
    log.setLevel(logging.DEBUG)
    log.propagate = False

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ── Console handler ────────────────────────────────────────────
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(fmt)
    log.addHandler(ch)

    # ── Rotating file handler ──────────────────────────────────────
    # Key the log file by logger name so different named loggers don't all
    # clobber the same "pipeline.log" (the default "daily_fact" logger
    # writes logs/daily_fact.log).
    logs_dir = os.path.join(REPO_ROOT, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    fh = logging.handlers.RotatingFileHandler(
        os.path.join(logs_dir, f"{name}.log"),
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    log.addHandler(fh)

    _LOGGERS[name] = log
    return log
