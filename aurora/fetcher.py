from __future__ import annotations
import re
import json
from datetime import datetime, timezone
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .config import RNCAN_EN, RNCAN_FR, NOAA_KP_URL, RAW_TO_LEVEL
from .models import RNCanSnapshot, ZoneForecast, KpPoint, ZoneName

HEADERS = {
    "User-Agent": "AurorA/0.1 (+https://github.com/f4k3id/aurora-forecast)"
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def _normalize_level(raw: str) -> Optional[str]:
    if not raw:
        return None
    s = raw.lower().strip()
    # direct
    if s in RAW_TO_LEVEL:
        return RAW_TO_LEVEL[s]
    # try to find keywords
    for key, val in RAW_TO_LEVEL.items():
        if key in s:
            return val
    return None


def _parse_rncan_text_block(text: str) -> tuple[str, dict[ZoneName, ZoneForecast]]:
    """
    Parse the ASCII art forecast block.
    Returns (issued_at, zones_dict)
    """
    # Example header:
    # 2026-06-08  Day of year 159  issued at 14:32 UT
    # or French: emis le 2026-06-08  (jour 159) a 14:32 TU
    # Try to capture full date + time
    issued_match = re.search(
        r"(\d{4}-\d{2}-\d{2}).*?(?:issued at|emis le|a)\s*([0-9:]+)\s*(UT|TU)?",
        text, re.IGNORECASE | re.DOTALL
    )
    if issued_match:
        date_part = issued_match.group(1)
        time_part = issued_match.group(2)
        tz = issued_match.group(3) or "UT"
        issued_at = f"{date_part} {time_part} {tz}"
    else:
        # Fallback older pattern
        issued_match2 = re.search(
            r"(?:issued at|emis le)\s*([0-9\-:\s]+(?:UT|TU))", text, re.IGNORECASE
        )
        issued_at = issued_match2.group(1).strip() if issued_match2 else datetime.now(timezone.utc).isoformat()

    sections = {}
    current_section = None

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        up = line.upper()
        if "LAST 24 HOURS" in up or "24 DERNIERES HEURES" in up:
            current_section = "last_24h"
            continue
        if "LAST 6 HOURS" in up or "6 DERNIERES HEURES" in up:
            current_section = "last_6h"
            continue
        if "NEXT 6 HOURS" in up or "6 PROCHAINES HEURES" in up:
            current_section = "next_6h"
            continue
        if "NEXT 24 HOURS" in up or "24 PROCHAINES HEURES" in up:
            current_section = "next_24h"
            continue

        if current_section:
            # Lines like:
            # POLAR        POL Active + Stormy intervals
            # AURORAL      AUR Unsettled + Stormy intervals
            # or French: POLAIRE      POL Active + période orageuses
            m = re.match(r"^(POLAR|POLAIRE|AURORAL|AURORALE|SUBAURORAL|SUBAURORALE)\s+(.+)$", line, re.IGNORECASE)
            if m:
                raw_zone = m.group(1).lower()
                content = m.group(2)

                if "polar" in raw_zone:
                    zone: ZoneName = "polar"
                elif "auror" in raw_zone:
                    zone = "auroral"
                else:
                    zone = "subauroral"

                level = _normalize_level(content)
                if zone not in sections:
                    sections[zone] = {}
                sections[zone][current_section] = level or content[:40]

    zones: dict[ZoneName, ZoneForecast] = {}
    for z in ("polar", "auroral", "subauroral"):
        if z in sections:
            zones[z] = ZoneForecast(
                zone=z,  # type: ignore
                last_24h=sections[z].get("last_24h"),
                last_6h=sections[z].get("last_6h"),
                next_6h=sections[z].get("next_6h"),
                next_24h=sections[z].get("next_24h"),
            )

    return issued_at, zones


def fetch_rncan(lang: str = "en") -> RNCanSnapshot:
    url = RNCAN_EN if lang == "en" else RNCAN_FR
    resp = SESSION.get(url, timeout=15)
    resp.raise_for_status()

    # Use html.parser (stdlib) — fast enough for RNCan pages and avoids pulling lxml (~8-10MB native libs)
    soup = BeautifulSoup(resp.text, "html.parser")

    # Prefer the clean text block
    # Look for the pre/code or the big text section
    text_block = ""
    # The page has a literal text forecast after "Forecast - Text"
    pre = soup.find("pre")
    if pre:
        text_block = pre.get_text("\n")
    else:
        # Fallback: find the big block with the ASCII header
        for tag in soup.find_all(["div", "p", "section"]):
            txt = tag.get_text(" ", strip=True)
            if "NATURAL RESOURCES CANADA" in txt or "RESSOURCES NATURELLES CANADA" in txt:
                text_block = txt
                break

    if not text_block:
        # Last resort: whole body text (messy but works for parser)
        text_block = soup.get_text("\n")

    issued_at, zones = _parse_rncan_text_block(text_block)

    # Extract useful official RNCan images (current conditions, forecasts, big chart)
    images = {}
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if "/generated_plots/forecast/plots/" in src:
            if "map-current" in src:
                images["current"] = src if src.startswith("http") else "https://www.spaceweather.gc.ca" + src
            elif "map-forecast_6" in src:
                images["forecast_6"] = src if src.startswith("http") else "https://www.spaceweather.gc.ca" + src
            elif "map-forecast_24" in src:
                images["forecast_24"] = src if src.startswith("http") else "https://www.spaceweather.gc.ca" + src
            elif "zon_rvw_frcst" in src:
                images["chart"] = src if src.startswith("http") else "https://www.spaceweather.gc.ca" + src

    return RNCanSnapshot(
        issued_at=issued_at,
        timestamp=datetime.now(timezone.utc).isoformat(),
        zones=zones,
        raw_text=text_block[:2000],
        images=images,
    )


def fetch_noaa_kp() -> tuple[Optional[KpPoint], list[KpPoint]]:
    """
    Returns (latest, history_list) from NOAA.
    The endpoint returns an array of 3-hourly points, most recent last.
    """
    resp = SESSION.get(NOAA_KP_URL, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    points: list[KpPoint] = []
    for item in data:
        try:
            kp = float(item.get("Kp", 0))
            pt = KpPoint(
                time_tag=item["time_tag"],
                kp=round(kp, 2),
                a_running=item.get("a_running"),
                station_count=item.get("station_count"),
            )
            points.append(pt)
        except Exception:
            continue

    latest = points[-1] if points else None
    return latest, points


def fetch_all() -> dict:
    """Convenience: fetch both sources."""
    rncan = None
    try:
        rncan = fetch_rncan("en")
    except Exception as e:
        print(f"[fetch] RNCan error: {e}")

    latest_kp = None
    kp_history = []
    try:
        latest_kp, kp_history = fetch_noaa_kp()
    except Exception as e:
        print(f"[fetch] NOAA Kp error: {e}")

    return {
        "rncan": rncan,
        "latest_kp": latest_kp,
        "kp_history": kp_history,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
