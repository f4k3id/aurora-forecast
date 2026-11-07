from __future__ import annotations
from pathlib import Path
import os

# App
APP_NAME = "AurorA"
VERSION = "0.2.0"

# Web server
WEB_HOST = "127.0.0.1"
WEB_PORT = int(os.getenv("AURORA_PORT", "8787"))

# Polling
POLL_INTERVAL_MINUTES = int(os.getenv("AURORA_POLL_MIN", "5"))

# Data dir
DATA_DIR = Path.home() / ".aurora"
DATA_DIR.mkdir(parents=True, exist_ok=True)

HISTORY_FILE = DATA_DIR / "history.json"
STATE_FILE = DATA_DIR / "last_state.json"

# RNCan URLs (we fetch EN for parsing, but support FR labels)
RNCAN_EN = "https://www.spaceweather.gc.ca/forecast-prevision/short-court/zone-en.php"
RNCAN_FR = "https://www.spaceweather.gc.ca/forecast-prevision/short-court/zone-fr.php"

# NOAA
NOAA_KP_URL = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"

# Zones we care about for "Stormy" alerts (normalized)
ALERT_ZONES = ["auroral", "polar"]  # can add "subauroral" if wanted

# Level ordering (for comparisons)
LEVEL_ORDER = {"quiet": 0, "unsettled": 1, "active": 2, "stormy": 3}

LEVEL_LABELS = {
    "en": {
        "quiet": "Quiet",
        "unsettled": "Unsettled",
        "active": "Active",
        "stormy": "Stormy",
    },
    "fr": {
        "quiet": "Calme",
        "unsettled": "Agitée",
        "active": "Active",
        "stormy": "Orageuse",
    },
}

ZONE_LABELS = {
    "en": {
        "polar": "Polar",
        "auroral": "Auroral",
        "subauroral": "Sub-Auroral",
    },
    "fr": {
        "polar": "Polaire",
        "auroral": "Aurorale",
        "subauroral": "Sub-Aurorale",
    },
}

# Map raw French/English words found in page to canonical
RAW_TO_LEVEL = {
    # English
    "quiet": "quiet",
    "unsettled": "unsettled",
    "active": "active",
    "stormy": "stormy",
    # French
    "calme": "quiet",
    "agitée": "unsettled",
    "agitee": "unsettled",
    "active": "active",
    "orageuse": "stormy",
    "orageuses": "stormy",
    "période orageuses": "stormy",
    "période active": "active",
}

# For display in UI (short status)
def get_level_label(level: str, lang: str = "en") -> str:
    return LEVEL_LABELS.get(lang, LEVEL_LABELS["en"]).get(level, level.title())

def get_zone_label(zone: str, lang: str = "en") -> str:
    return ZONE_LABELS.get(lang, ZONE_LABELS["en"]).get(zone, zone.title())
