import logging
import sys

import structlog


def configure_logging(*, production: bool = False) -> None:
    renderer = (
        structlog.processors.JSONRenderer() if production else structlog.dev.ConsoleRenderer()
    )
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=logging.INFO, force=True)
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=False,
    )
