from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def utc_iso(dt: datetime | None = None) -> str:
    value = dt or utc_now()
    return value.replace(microsecond=0).isoformat() + "Z"
