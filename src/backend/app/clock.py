"""Time source. All timestamps are stored as UTC ISO-8601 strings."""
from datetime import UTC, datetime


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
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def iso_week(value: str) -> str:
    year, week, _ = parse_iso(value).isocalendar()
    return f"{year}-W{week:02d}"
