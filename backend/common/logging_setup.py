"""Configure structured application logging with request IDs and secret redaction."""

import logging
from collections.abc import Iterable

from backend.common.log_filters import SecretsFilter
from backend.common.request_id import RequestIdFilter

LOG_FORMAT = "%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"


def configure_logging(level: str, secrets: Iterable[str] = ()) -> None:
    """Set root logging level, a consistent format, and security filters.

    Args:
        level: Logging level name, such as ``INFO`` or ``WARNING``.
        secrets: Configured values that must be redacted from messages and tracebacks.
    """
    numeric_level = getattr(logging, str(level).upper(), logging.INFO)
    if not isinstance(numeric_level, int):
        numeric_level = logging.INFO

    logging.basicConfig(level=numeric_level, format=LOG_FORMAT)
    root = logging.getLogger()
    root.setLevel(numeric_level)

    secret_filter = SecretsFilter(tuple(secrets))
    for handler in root.handlers:
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        if not any(isinstance(item, RequestIdFilter) for item in handler.filters):
            handler.addFilter(RequestIdFilter())
        if not any(isinstance(item, SecretsFilter) for item in handler.filters):
            handler.addFilter(secret_filter)
