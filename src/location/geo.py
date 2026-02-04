"""Offline location helpers for geolocation coordinates."""

from __future__ import annotations

from typing import Optional, Tuple

try:
    import reverse_geocoder as rg
except Exception:  # pragma: no cover - optional dependency
    rg = None


def resolve_location_from_coords(lat: float, lon: float) -> Tuple[Optional[str], Optional[str]]:
    """
    Resolve a coarse location and country code from coordinates.

    Returns:
        (location_string, country_code)
    """
    if rg is None:
        return None, None

    try:
        results = rg.search((lat, lon))
        if not results:
            return None, None

        entry = results[0]
        city = entry.get("name")
        region = entry.get("admin1")
        country_code = entry.get("cc")

        if city and region:
            location = f"{city}, {region}"
        else:
            location = city or region

        return location, country_code
    except Exception:
        return None, None
