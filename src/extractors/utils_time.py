from __future__ import annotations

import datetime as _dt
from typing import Any, Optional

def _to_datetime(value: Any) -> Optional[_dt.datetime]:
    """
    Convert a variety of timestamp formats into a timezone-aware UTC datetime.
    Supported formats:
      - ISO 8601 strings
      - Unix timestamps (int or float, seconds)
    """
    if value is None:
        return None

    # Already datetime
    if isinstance(value, _dt.datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=_dt.timezone.utc)
        return value.astimezone(_dt.timezone.utc)

    # Unix timestamp
    if isinstance(value, (int, float)):
        try:
            return _dt.datetime.fromtimestamp(float(value), tz=_dt.timezone.utc)
        except (OverflowError, OSError):
            return None

    # ISO 8601 string
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None

        # Basic normalization for trailing Z
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"

        # Try several common formats
        formats = [
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%d %H:%M:%S%z",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ]
        for fmt in formats:
            try:
                dt = _dt.datetime.strptime(text, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=_dt.timezone.utc)
                return dt.astimezone(_dt.timezone.utc)
            except ValueError:
                continue

    return None

def normalize_timestamp(value: Any) -> str:
    """
    Normalize a Snapchat timestamp-like value into an ISO8601 UTC string.
    If parsing fails, returns an empty string.
    """
    dt = _to_datetime(value)
    if dt is None:
        return ""
    return dt.astimezone(_dt.timezone.utc).isoformat().replace("+00:00", "Z")