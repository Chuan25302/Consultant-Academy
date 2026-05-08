import io
import logging
import sys


def setup_logger(name: str) -> logging.Logger:
    root = logging.getLogger()
    if not root.handlers:
        stream = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace", line_buffering=True) \
            if hasattr(sys.stdout, "buffer") else sys.stdout
        h = logging.StreamHandler(stream)
        h.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
            datefmt="%H:%M:%S"
        ))
        root.addHandler(h)
        root.setLevel(logging.INFO)
    return logging.getLogger(name)
