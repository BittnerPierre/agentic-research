"""Logging configuration for agentic-research."""

import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path


def _parse_log_level(log_level: str, default: int = logging.INFO) -> tuple[int, bool]:
    """
    Convertit une valeur de niveau de log en int logging.*.
    Fallback sur INFO si la valeur est invalide.
    """
    if isinstance(log_level, int):
        return log_level, True

    level_name = str(log_level).upper()
    level = logging._nameToLevel.get(level_name)  # type: ignore[attr-defined]
    if isinstance(level, int) and level > 0:
        return level, True
    return default, False


def setup_run_logging(log_dir: str = "logs", log_level: str = "INFO") -> Path:
    """
    Set up logging for a single run with timestamped log file.

    Args:
        log_dir: Directory to store log files
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Path to the log file created
    """
    # Create logs directory
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # Create timestamped log file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_path / f"run_{timestamp}.log"

    # Configure logging format
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Get root logger
    root_logger = logging.getLogger()
    # IMPORTANT: garder le root en DEBUG pour que le handler fichier capte bien les DEBUG
    root_logger.setLevel(logging.DEBUG)

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # File handler - detailed logging
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)  # Always capture DEBUG in file
    file_formatter = logging.Formatter(log_format, datefmt=date_format)
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # Console handler - less verbose
    console_handler = logging.StreamHandler(sys.stdout)
    console_level, is_valid = _parse_log_level(log_level, default=logging.INFO)
    console_handler.setLevel(console_level)
    console_formatter = logging.Formatter(log_format, datefmt=date_format)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # Log startup info
    root_logger.info("=" * 80)
    root_logger.info(f"Starting new run - Log file: {log_file}")
    if not is_valid:
        root_logger.warning(
            f"Invalid log_level={log_level!r} provided, using {logging.getLevelName(console_level)}"
        )
    root_logger.info("=" * 80)

    return log_file


def setup_server_logging(
    log_dir: str = "logs",
    log_level: str = "INFO",
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
) -> Path:
    """
    Set up logging for long-running server with rotating file handler.

    Args:
        log_dir: Directory to store log files
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        max_bytes: Maximum size of log file before rotation (default 10MB)
        backup_count: Number of backup files to keep (default 5)

    Returns:
        Path to the log file
    """
    # Create logs directory
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # Server log file (no timestamp, will rotate)
    log_file = log_path / "dataprep_server.log"

    # Configure logging format
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Get root logger
    root_logger = logging.getLogger()
    # IMPORTANT: garder le root en DEBUG pour que le handler fichier capte bien les DEBUG
    root_logger.setLevel(logging.DEBUG)

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Rotating file handler
    file_handler = RotatingFileHandler(
        log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)  # Always capture DEBUG in file
    file_formatter = logging.Formatter(log_format, datefmt=date_format)
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # Console handler - less verbose
    console_handler = logging.StreamHandler(sys.stdout)
    console_level, is_valid = _parse_log_level(log_level, default=logging.INFO)
    console_handler.setLevel(console_level)
    console_formatter = logging.Formatter(log_format, datefmt=date_format)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # Log startup info
    root_logger.info("=" * 80)
    root_logger.info(f"Server starting - Log file: {log_file}")
    root_logger.info(f"Log rotation: max_bytes={max_bytes}, backup_count={backup_count}")
    if not is_valid:
        root_logger.warning(
            f"Invalid log_level={log_level!r} provided, using {logging.getLevelName(console_level)}"
        )
    root_logger.info("=" * 80)

    return log_file


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name.

    This is a convenience function that returns a logger which will
    use the handlers configured by setup_run_logging() or setup_server_logging().

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
