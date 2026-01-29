"""Time utilities for timestamps. All datetimes in UTC."""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return current UTC datetime. Use for created_at/updated_at."""
    return datetime.now(timezone.utc)
