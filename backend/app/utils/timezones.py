from datetime import date, datetime, time, timedelta, timezone

from app.config.constants import LONDON


def parse_instant(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a UTC offset")
    return parsed.astimezone(timezone.utc)


def parse_instant_or_local(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=LONDON).astimezone(timezone.utc)
    return parsed.astimezone(timezone.utc)


def to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def to_london(value: datetime) -> datetime:
    return to_utc(value).astimezone(LONDON)


def format_london(value: datetime | None) -> str | None:
    if value is None:
        return None
    return to_london(value).isoformat()


def format_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    return to_utc(value).strftime("%Y-%m-%dT%H:%M:%SZ")


def london_midnight_utc(day: date) -> datetime:
    return datetime.combine(day, time(0, 0), tzinfo=LONDON).astimezone(timezone.utc)


def delivery_day_bounds_utc(day: date) -> tuple[datetime, datetime]:
    start = london_midnight_utc(day)
    end = london_midnight_utc(day + timedelta(days=1))
    return start, end


def period_grid(start: datetime, end: datetime, step_minutes: int) -> list[datetime]:
    step = timedelta(minutes=step_minutes)
    grid: list[datetime] = []
    cursor = to_utc(start)
    limit = to_utc(end)
    while cursor < limit:
        grid.append(cursor)
        cursor = cursor + step
    return grid


def floor_to_hour(value: datetime) -> datetime:
    return to_utc(value).replace(minute=0, second=0, microsecond=0)


def parse_date(value: str) -> date:
    return date.fromisoformat(value.strip())
