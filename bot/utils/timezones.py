"""Shared timezone configuration for bot settings."""

from __future__ import annotations

from datetime import datetime, timezone as dt_timezone
from typing import Any

try:  # Python >=3.9 ships with zoneinfo
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - fallback for very old runtimes
    ZoneInfo = None  # type: ignore[assignment]

TIMEZONE_CHOICES: list[tuple[str, str, str]] = [
    ("UTC", "UTC", "UTC (Coordinated Universal Time)"),
    ("Africa/Johannesburg", "🇿🇦 South Africa", "South Africa (UTC+02:00)"),
    ("Europe/London", "🇬🇧 United Kingdom", "United Kingdom (UTC+00:00)"),
    ("America/New_York", "🇺🇸 United States", "United States (New York, UTC-05:00)"),
    ("Asia/Tokyo", "🇯🇵 Japan", "Japan (UTC+09:00)"),
]

TIMEZONE_LABEL_MAP = {code: label for code, label, _ in TIMEZONE_CHOICES}
TIMEZONE_DESCRIPTION_MAP = {code: description for code, _, description in TIMEZONE_CHOICES}


def _get_zoneinfo(timezone_code: str) -> Any:
    """Return ZoneInfo for the given timezone code with UTC fallback."""

    if ZoneInfo is None:
        return None

    try:
        return ZoneInfo(timezone_code)
    except Exception:  # pragma: no cover - fallback for invalid codes
        return ZoneInfo("UTC")


def parse_datetime(value: datetime | str | None) -> datetime | None:
    """Parse incoming datetime value allowing ISO strings and aware objects."""

    if value is None:
        return None

    if isinstance(value, datetime):
        return value

    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return None

        # Normalize trailing "Z" to ISO8601 timezone
        if candidate.endswith("Z"):
            candidate = candidate[:-1] + "+00:00"

        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            return None

    return None


def to_local_datetime(value: datetime | str | None, timezone_code: str = "UTC") -> datetime | None:
    """Convert a datetime or ISO string to the user's timezone."""

    dt_value = parse_datetime(value)
    if dt_value is None:
        return None

    if dt_value.tzinfo is None:
        dt_value = dt_value.replace(tzinfo=dt_timezone.utc)

    tz_obj = _get_zoneinfo(timezone_code) or dt_timezone.utc
    try:
        return dt_value.astimezone(tz_obj)
    except Exception:  # pragma: no cover - fallback for unexpected issues
        return dt_value.astimezone(dt_timezone.utc)


def format_datetime_for_user(
    value: datetime | str | None,
    timezone_code: str = "UTC",
    fmt: str = "%Y-%m-%d %H:%M:%S %Z",
) -> str | None:
    """Format a datetime/ISO string into the user's timezone using the given format."""

    localized = to_local_datetime(value, timezone_code)
    if localized is None:
        return None

    try:
        return localized.strftime(fmt)
    except Exception:  # pragma: no cover
        return None


__all__ = [
    "TIMEZONE_CHOICES",
    "TIMEZONE_LABEL_MAP",
    "TIMEZONE_DESCRIPTION_MAP",
    "parse_datetime",
    "to_local_datetime",
    "format_datetime_for_user",
]
