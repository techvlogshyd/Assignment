from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional


def configure_logging(log_dir: Path, level: Optional[str] = None) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    resolved = (level or os.environ.get("INTEGRATION_LOG_LEVEL") or "INFO").upper()
    handlers: list[logging.Handler] = [
        logging.StreamHandler(),
        logging.FileHandler(log_dir / "integration.log", encoding="utf-8"),
    ]
    logging.basicConfig(
        level=getattr(logging, resolved, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
        handlers=handlers,
        force=True,
    )

