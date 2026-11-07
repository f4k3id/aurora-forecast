from __future__ import annotations
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Callable, Optional

from .config import POLL_INTERVAL_MINUTES, ALERT_ZONES, LEVEL_ORDER
from .fetcher import fetch_all
from .models import CurrentState
from .store import load_state, save_state, append_kp_history
from .notifier import notify_stormy

LEVEL_TO_SCORE = {
    "quiet": 0,
    "unsettled": 1,
    "active": 2,
    "stormy": 3,
}


def _get_current_activity_point(state: CurrentState) -> dict | None:
    """Compute the current local activity score (0-3) from the latest RNCan snapshot."""
    if not state.rncan or not state.rncan.zones:
        return None
    aur = state.rncan.zones.get("auroral")
    score = 0
    label = "—"
    if aur and aur.next_6h:
        score = LEVEL_TO_SCORE.get(aur.next_6h, 0)
        label = aur.next_6h
    else:
        # fallback: max score from any zone's next_6h
        for z in state.rncan.zones.values():
            if z.next_6h:
                s = LEVEL_TO_SCORE.get(z.next_6h, 0)
                if s > score:
                    score = s
                    label = z.next_6h
    return {
        "t": state.last_fetch or datetime.now(timezone.utc).isoformat(),
        "score": score,
        "label": label,
    }


def get_activity_history_for_ui(state: CurrentState) -> list[dict]:
    """History for the chart, guaranteed to contain at least the current observation
    when RNCan data is present. This ensures the UI always has something to render
    immediately (the background scheduler accumulates the trend over polls).
    """
    hist = list(state.activity_history or [])
    if state.rncan and state.rncan.zones:
        point = _get_current_activity_point(state)
        if point:
            # append current only if it differs from the last stored point (avoid spamming identical quiet)
            if not hist or hist[-1].get("score") != point.get("score"):
                hist = hist + [point]
            hist = hist[-48:]
    return hist

# Global shared state (simple for a local app)
_state: CurrentState = load_state()
_lock = threading.Lock()
_running = False
_thread: Optional[threading.Thread] = None

# Callback for UI refresh (optional)
_on_update: Optional[Callable[[CurrentState], None]] = None


def get_state() -> CurrentState:
    with _lock:
        return _state


def set_update_callback(cb: Callable[[CurrentState], None]):
    global _on_update
    _on_update = cb


def _detect_new_stormy(old_state: CurrentState, new_rncan_zones: dict, latest_kp) -> list[tuple[str, str]]:
    """
    Return list of (zone, level) that just became stormy (or contain stormy) since last check.
    """
    alerts = []
    for zone in ALERT_ZONES:
        new_zone = new_rncan_zones.get(zone)
        if not new_zone:
            continue

        # Check next_6h and next_24h for "stormy"
        is_stormy_now = False
        current_level = None
        for period in ("next_6h", "next_24h"):
            lvl = getattr(new_zone, period, None)
            if lvl == "stormy":
                is_stormy_now = True
                current_level = "stormy"
                break

        if not is_stormy_now:
            continue

        # Was it already stormy last time?
        was_stormy = zone in (old_state.last_stormy_zones or set())
        if not was_stormy:
            alerts.append((zone, current_level or "stormy"))

    return alerts


def _do_fetch_and_update() -> CurrentState:
    global _state

    print(f"[scheduler] Fetching data... ({datetime.now(timezone.utc).isoformat()})")
    fetched = fetch_all()

    with _lock:
        old_state = _state
        new_state = CurrentState(
            rncan=fetched.get("rncan"),
            latest_kp=fetched.get("latest_kp"),
            last_fetch=fetched.get("fetched_at"),
        )

        # Merge Kp history
        if fetched.get("kp_history"):
            append_kp_history(new_state, fetched["kp_history"])

        # Keep previous history if fetch failed for Kp this time
        if not new_state.kp_history and old_state.kp_history:
            new_state.kp_history = old_state.kp_history

        # Carry over previous activity history (persisted across fetches; fetcher does not provide it)
        new_state.activity_history = list(old_state.activity_history) if old_state else []

        # Trim ancient points (keep only last ~24h worth; the [-48:] below is a hard cap)
        if new_state.activity_history:
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
            new_state.activity_history = [p for p in new_state.activity_history if p.get("t", "") >= cutoff]

        # Compute and append simple activity score history (for charts)
        if new_state.rncan and new_state.rncan.zones:
            point = _get_current_activity_point(new_state)
            if point:
                new_state.activity_history.append(point)
                # keep last ~48 points (~4h at 5min poll, or more across restarts)
                new_state.activity_history = new_state.activity_history[-48:]

        # Stormy detection + notifications
        if new_state.rncan and new_state.rncan.zones:
            # Only notify if we had a previous persisted state (avoid first-run spam)
            had_previous = bool(old_state.last_fetch or old_state.rncan)

            new_stormies = _detect_new_stormy(old_state, new_state.rncan.zones, new_state.latest_kp)
            for zone, level in new_stormies:
                if had_previous:
                    kp_val = new_state.latest_kp.kp if new_state.latest_kp else None
                    print(f"[scheduler] !!! STORMY detected: {zone} -> {level} (Kp={kp_val})")
                    notify_stormy(zone, level, kp=kp_val, lang="en")
                    notify_stormy(zone, level, kp=kp_val, lang="fr")
                else:
                    print(f"[scheduler] Stormy present on startup (no notification): {zone}")

            # Update the set of zones currently in stormy state
            current_stormy = set()
            for zname, zf in new_state.rncan.zones.items():
                if any(getattr(zf, p, None) == "stormy" for p in ("next_6h", "next_24h")):
                    current_stormy.add(zname)
            new_state.last_stormy_zones = current_stormy

        # Persist
        _state = new_state
        save_state(_state)

        if _on_update:
            try:
                _on_update(_state)
            except Exception:
                pass

        return _state


def _scheduler_loop():
    global _running
    _running = True
    # First immediate fetch
    try:
        _do_fetch_and_update()
    except Exception as e:
        print(f"[scheduler] initial fetch error: {e}")

    while _running:
        time.sleep(POLL_INTERVAL_MINUTES * 60)
        if not _running:
            break
        try:
            _do_fetch_and_update()
        except Exception as e:
            print(f"[scheduler] loop error: {e}")


def start_scheduler():
    global _thread, _running
    if _thread and _thread.is_alive():
        print("[scheduler] already running")
        return

    _thread = threading.Thread(target=_scheduler_loop, daemon=True, name="aurora-scheduler")
    _thread.start()
    print(f"[scheduler] started (every {POLL_INTERVAL_MINUTES} min)")


def stop_scheduler():
    global _running
    _running = False
    print("[scheduler] stop requested")


def force_refresh() -> CurrentState:
    """Manual refresh from UI or menubar."""
    return _do_fetch_and_update()
