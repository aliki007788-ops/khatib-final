from __future__ import annotations

import logging
import sys

from pythonjsonlogger import jsonlogger


def configure_logging(debug: bool = False) -> None:
    logger = logging.getLogger()

    logger.handlers.clear()
    logger.setLevel(logging.DEBUG if debug else logging.INFO)

    handler = logging.StreamHandler(sys.stdout)

    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s "
        "%(message)s %(request_id)s"
    )

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
