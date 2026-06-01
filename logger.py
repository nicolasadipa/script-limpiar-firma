"""
logger.py — Configuración del sistema de logging.

Escribe simultáneamente en consola y en un archivo de log rotativo.
Cada línea incluye: timestamp, nivel, nombre del módulo y mensaje.
"""

import logging
import os
from logging.handlers import RotatingFileHandler

import config


def setup_logger(name: str = "firma_processor") -> logging.Logger:
    """
    Crea y devuelve un logger configurado con dos handlers:
      - StreamHandler  → consola (nivel INFO)
      - RotatingFileHandler → archivo en logs/ (nivel DEBUG, hasta 5 MB × 3 backups)
    """
    os.makedirs(config.LOG_DIR, exist_ok=True)

    log_path = os.path.join(config.LOG_DIR, config.LOG_FILENAME)

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Evitar duplicar handlers si el logger ya existe
    if logger.handlers:
        return logger

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(module)-18s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # -- Handler de consola --
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(fmt)

    # -- Handler de archivo --
    file_handler = RotatingFileHandler(
        log_path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger
