"""Clock helpers with an explicit UTC source and SQLite-compatible values."""
from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return UTC as a naive datetime for the existing SQLite DateTime schema."""
    return datetime.now(UTC).replace(tzinfo=None)
