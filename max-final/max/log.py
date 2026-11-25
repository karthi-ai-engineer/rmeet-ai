"""
Logging: one file per program in data/logs/<name>.log, plus short console output.

  log = setup_logging("max", data_dir, secrets=[api_key])

Any secret value passed in is replaced by *** in every log line, tracebacks included.
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


class RedactingFormatter(logging.Formatter):
    def __init__(self, secrets: list[str]):
        super().__init__(FORMAT)
        self.secrets = [s for s in secrets if s and len(s) >= 6]

    def format(self, record: logging.LogRecord) -> str:
        text = super().format(record)
        for s in self.secrets:
            text = text.replace(s, "***")
        return text


def setup_logging(name: str, data_dir: Path, level: str = "INFO", secrets: list[str] | None = None,
                  console_level: str = "WARNING") -> logging.Logger:
    log_dir = Path(data_dir) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(level.upper())
    for h in list(root.handlers):          # calling it twice must not double every line
        if getattr(h, "_max_handler", False):
            root.removeHandler(h)
            h.close()
    formatter = RedactingFormatter(secrets or [])

    file_h = logging.handlers.RotatingFileHandler(log_dir / f"{name}.log", maxBytes=5_000_000,
                                                  backupCount=3, encoding="utf-8")
    console_h = logging.StreamHandler()
    console_h.setLevel(console_level.upper())
    for h in (file_h, console_h):
        h.setFormatter(formatter)
        h._max_handler = True
        root.addHandler(h)
    for noisy in ("httpx", "httpx2", "httpcore", "google_genai"):
        logging.getLogger(noisy).setLevel("WARNING")
    return logging.getLogger(name)
