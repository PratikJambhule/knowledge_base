import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any
from uuid import uuid4


def configure_logging(log_path: str) -> None:
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not logging.getLogger().handlers:
        handler = RotatingFileHandler(path, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(message)s"))
        logging.basicConfig(level=logging.INFO, handlers=[handler])


def log_event(event_type: str, **fields: Any) -> str:
    correlation_id = fields.pop("correlation_id", str(uuid4()))
    payload = {"event": event_type, "correlation_id": correlation_id, **fields}
    logging.getLogger("knowledgebridge").info(json.dumps(payload, default=str))
    return correlation_id
