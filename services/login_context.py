"""Turn a login request's IP and User-Agent into something a person can recognise,
e.g. "Chrome on Windows" from "Lagos, Nigeria"."""
import ipaddress
import logging
import re
import time
from typing import Dict, Optional, Tuple

import httpx

from config import settings

logger = logging.getLogger(__name__)

# ipwho.is answers without a key; with IPWHOIS_KEY set we use the paid endpoint for higher limits
IPWHOIS_FREE_URL = "https://ipwho.is/{ip}"
IPWHOIS_PAID_URL = "https://ipwhois.pro/{ip}"

# The same user usually signs in from the same IP, so remember answers for a day
_CACHE_TTL_SECONDS = 24 * 60 * 60
_CACHE_MAX_ENTRIES = 5000
_location_cache: Dict[str, Tuple[float, Optional[str]]] = {}

# Order matters: Edge/Opera/Samsung UAs also contain "Chrome", and Chrome UAs contain "Safari"
_BROWSERS = [
    (r"Edg(e|A|iOS)?/", "Edge"),
    (r"OPR/|Opera", "Opera"),
    (r"SamsungBrowser/", "Samsung Internet"),
    (r"CriOS/|Chrome/", "Chrome"),
    (r"FxiOS/|Firefox/", "Firefox"),
    (r"Version/.*Safari/", "Safari"),
    (r"PostmanRuntime/", "Postman"),
    (r"^curl/", "curl"),
]
_OPERATING_SYSTEMS = [
    (r"iPhone", "iPhone"),
    (r"iPad", "iPad"),
    (r"Android", "Android"),
    (r"Windows NT", "Windows"),
    (r"CrOS", "ChromeOS"),
    (r"Mac OS X|Macintosh", "macOS"),
    (r"Linux", "Linux"),
]


def describe_device(user_agent: Optional[str]) -> Optional[str]:
    """Summarise a User-Agent as "<browser> on <OS>", falling back to whichever part is known."""
    if not user_agent:
        return None
    browser = next((name for pattern, name in _BROWSERS if re.search(pattern, user_agent)), None)
    os_name = next((name for pattern, name in _OPERATING_SYSTEMS if re.search(pattern, user_agent)), None)
    if browser and os_name:
        return f"{browser} on {os_name}"
    return browser or os_name or "Unknown device"


async def lookup_location(ip_address: Optional[str]) -> Optional[str]:
    """Approximate "City, Region, Country" for a public IP, or None if it can't be determined.

    Never raises: a failed lookup just means the notification goes out without a location.
    """
    if not ip_address:
        return None
    try:
        if not ipaddress.ip_address(ip_address).is_global:
            return None  # localhost / private network addresses have no location
    except ValueError:
        return None

    cached = _location_cache.get(ip_address)
    if cached and cached[0] > time.monotonic():
        return cached[1]

    if settings.IPWHOIS_KEY:
        url, params = IPWHOIS_PAID_URL.format(ip=ip_address), {"key": settings.IPWHOIS_KEY}
    else:
        url, params = IPWHOIS_FREE_URL.format(ip=ip_address), None
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            response = await client.get(url, params=params)
        data = response.json()
    except Exception as exc:
        logger.warning("IP location lookup failed for %s: %s", ip_address, exc)
        return None  # Not cached, so the next login retries

    if response.status_code != 200 or not data.get("success"):
        logger.warning("IP location lookup failed for %s: %s %s", ip_address, response.status_code, data.get("message"))
        return None

    # De-duplicate so e.g. "Lagos, Lagos, Nigeria" reads as "Lagos, Nigeria"
    parts = []
    for part in (data.get("city"), data.get("region"), data.get("country")):
        if part and part not in parts:
            parts.append(part)
    location = ", ".join(parts) or None

    if len(_location_cache) >= _CACHE_MAX_ENTRIES:
        _location_cache.clear()
    _location_cache[ip_address] = (time.monotonic() + _CACHE_TTL_SECONDS, location)
    return location
