from __future__ import annotations
import json
from datetime import datetime, timezone, timedelta
from typing import Optional

from .config import HISTORY_FILE, STATE_FILE
from .models import CurrentState, KpPoint, RNCanSnapshot


def _load_json(path) -> Optional[dict]:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def _save_json(path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_state() -> CurrentState:
    data = _load_json(STATE_FILE)
    if data:
        try:
            return CurrentState.from_dict(data)
        except Exception:
            pass
    return CurrentState()


def save_state(state: CurrentState):
    _save_json(STATE_FILE, state.to_dict())


def load_history() -> list[dict]:
    data = _load_json(HISTORY_FILE)
    return data.get("snapshots", []) if data else []


def save_history(snapshots: list[dict]):
    _save_json(HISTORY_FILE, {"snapshots": snapshots, "updated": datetime.now(timezone.utc).isoformat()})


def append_kp_history(state: CurrentState, new_points: list[KpPoint], max_age_hours: int = 200):
    """Merge new Kp points into state.kp_history, keep unique by time_tag, trim old.
    Increased to ~8 days to support 7-day Kp chart."""
    existing = {p.time_tag: p for p in state.kp_history}
    for p in new_points:
        existing[p.time_tag] = p

    # sort + trim
    sorted_points = sorted(existing.values(), key=lambda p: p.time_tag)
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=max_age_hours)).isoformat()
    trimmed = [p for p in sorted_points if p.time_tag >= cutoff]
    state.kp_history = trimmed


def get_recent_kp_for_chart(state: CurrentState, hours: int = 30) -> list[dict]:
    """Return list ready for Chart.js (last N hours)."""
    if not state.kp_history:
        return []
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    recent = [p for p in state.kp_history if p.time_tag >= cutoff]
    return [
        {
            "t": p.time_tag,
            "kp": p.kp,
        }
        for p in sorted(recent, key=lambda x: x.time_tag)
    ]
