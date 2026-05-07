import io
import logging
import sys


def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        stream = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") \
            if hasattr(sys.stdout, "buffer") else sys.stdout
        h = logging.StreamHandler(stream)
        h.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
            datefmt="%H:%M:%S"
        ))
        logger.addHandler(h)
        logger.setLevel(logging.INFO)
    return logger
