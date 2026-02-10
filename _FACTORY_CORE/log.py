"""
Factory Logger - Unified logging for foreground and daemon mode
===============================================================
Replaces per-module print()-based log() functions that are lost in daemon mode.

Every module uses get_logger() which:
- Always writes to rotating file (data/logs/{name}-{project}.log)
- Also prints to stdout in foreground mode
- Format: [TIMESTAMP] [NAME] [LEVEL] message

Usage:
    from core.log import get_logger

    logger = get_logger("wiggum-tdd", "ppz")
    logger.info("Starting task: task-001")
    logger.warn("Build timeout")
    logger.error("Process killed")
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

_LOG_DIR = Path(__file__).parent.parent / "data" / "logs"
_loggers = {}


class FactoryLogger:
    """Logger that works in both foreground and daemon mode."""

    def __init__(self, name: str, project: str = None):
        self.name = name
        suffix = f"-{project}" if project else ""
        self.logger_name = f"{name}{suffix}"

        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_file = _LOG_DIR / f"{self.logger_name}.log"

        self._logger = logging.getLogger(f"factory.{self.logger_name}")
        self._logger.setLevel(logging.DEBUG)

        # Avoid duplicate handlers on repeated get_logger() calls
        if not self._logger.handlers:
            # File handler (always active, works in daemon mode)
            fh = RotatingFileHandler(
                log_file, maxBytes=10 * 1024 * 1024, backupCount=5,
            )
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(logging.Formatter(
                "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            ))
            self._logger.addHandler(fh)

            # Stdout handler (for foreground; in daemon mode stdout goes to log file via dup2)
            sh = logging.StreamHandler(sys.stdout)
            sh.setLevel(logging.INFO)
            sh.setFormatter(logging.Formatter(
                "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
                datefmt="%H:%M:%S",
            ))
            self._logger.addHandler(sh)

    def info(self, msg: str):
        self._logger.info(msg)

    def warn(self, msg: str):
        self._logger.warning(msg)

    def error(self, msg: str):
        self._logger.error(msg)

    def debug(self, msg: str):
        self._logger.debug(msg)

    def log(self, msg: str, level: str = "INFO"):
        """Legacy-compatible log method (accepts level as string)."""
        level_map = {
            "DEBUG": self.debug,
            "INFO": self.info,
            "WARN": self.warn,
            "WARNING": self.warn,
            "ERROR": self.error,
        }
        fn = level_map.get(level.upper(), self.info)
        fn(msg)

    def __call__(self, msg: str, level: str = "INFO"):
        """Allow logger("msg", "WARN") syntax for drop-in replacement of log() functions."""
        self.log(msg, level)


def get_logger(name: str, project: str = None) -> FactoryLogger:
    """
    Get or create a FactoryLogger.

    Args:
        name: Module name (e.g., "wiggum-tdd", "adversarial", "brain")
        project: Project ID (e.g., "ppz", "veligo"). Appended to log filename.

    Returns:
        FactoryLogger instance (cached per name+project)
    """
    key = f"{name}-{project}" if project else name
    if key not in _loggers:
        _loggers[key] = FactoryLogger(name, project)
    return _loggers[key]
