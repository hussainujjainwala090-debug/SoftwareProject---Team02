"""Time source. All timestamps are stored as UTC ISO-8601 strings."""
from datetime import datetime, timezone

UTC = timezone.utc  # datetime.UTC needs Python 3.11; the project supports 3.10+


class Clock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FixedClock(Clock):
    """Settable clock for tests (e.g. to age the weather cache)."""

    def __init__(self, at: datetime) -> None:
        self.at = at

    def now(self) -> datetime:
        return self.at


def to_iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat(timespec="seconds")


def parse_iso(value: str) -> datetime:
    # Python 3.10 does not accept a trailing "Z" in fromisoformat.
    dt = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def iso_week(value: str) -> str:
    year, week, _ = parse_iso(value).isocalendar()
    return f"{year}-W{week:02d}"
