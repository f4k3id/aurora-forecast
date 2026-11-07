#!/usr/bin/env python3
"""
AurorA - macOS Menu Bar App (🌌)

This is the main entry point for both:
  - Direct execution: python menubar.py
  - Packaged .app built with py2app

It provides:
  - Native menu bar icon + status (Kp + zone level)
  - Embedded web dashboard on localhost
  - 5-minute background sync + macOS notifications for "Stormy"
"""
from __future__ import annotations
import os
import sys
import threading
import webbrowser
import traceback
from datetime import datetime
from pathlib import Path

# --- Robust logging (very useful inside .app bundles) ---
LOG_DIR = Path.home() / "Library" / "Logs" / "AurorA"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "aurora.log"

def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

# Try to import rumps early
try:
    import rumps
except ImportError as e:
    rumps = None
    log(f"WARNING: rumps not available: {e}")

from aurora.config import APP_NAME, WEB_HOST, WEB_PORT, POLL_INTERVAL_MINUTES, VERSION
from aurora.scheduler import start_scheduler, get_state, force_refresh



def _start_web_server_in_thread():
    """Run the Flask web dashboard in a daemon thread (lightweight, no uvicorn/FastAPI)."""
    def _run():
        # Import here so the menubar entry doesn't hard-require Flask at import time
        # (useful for the rumps fallback path and slightly faster cold start).
        from aurora.web.server import app as web_app
        log(f"Starting embedded web server on http://{WEB_HOST}:{WEB_PORT}")
        # Flask dev server (Werkzeug) is perfectly fine for a local single-user dashboard.
        # threaded=True allows the UI's 60s polling + manual refresh to coexist.
        web_app.run(
            host=WEB_HOST,
            port=WEB_PORT,
            debug=False,
            use_reloader=False,
            threaded=True,
        )

    t = threading.Thread(target=_run, daemon=True, name="aurora-web")
    t.start()
    return t


def _show_fallback_notification(title: str, subtitle: str = ""):
    """Best-effort macOS notification even if rumps failed."""
    try:
        import subprocess
        script = f'display notification "{subtitle}" with title "{title}"'
        subprocess.run(["osascript", "-e", script], check=False, timeout=3)
    except Exception:
        pass


class AurorAMenuBar(rumps.App):
    def __init__(self):
        # template=True makes the icon adapt to light/dark menu bar
        super().__init__(APP_NAME, icon=None, template=True, quit_button=None)

        self.menu = [
            rumps.MenuItem("🌐  Open Dashboard", callback=self.open_dashboard),
            rumps.MenuItem("⟳  Refresh Now", callback=self.refresh_now),
            None,
            rumps.MenuItem("Last update: —", callback=None),
            rumps.MenuItem(f"Version {VERSION}", callback=None),
            None,
            rumps.MenuItem("Quit AurorA", callback=self.quit_app),
        ]

        self.title = "🌌 —"

        log("Starting AurorA menubar services...")
        self.web_thread = _start_web_server_in_thread()
        start_scheduler()

        # Update title periodically
        self.timer = rumps.Timer(self._update_title, 25)
        self.timer.start()

        # Quick initial title refresh (one-shot)
        threading.Timer(2.5, lambda: self._update_title(None)).start()

        # One-time "first launch ever" welcome notification (not on every app start)
        threading.Timer(5, lambda: _show_startup_message(self)).start()

    def _get_short_status(self) -> str:
        state = get_state()
        parts = []

        if state.latest_kp:
            kp = state.latest_kp.kp
            parts.append(f"Kp{kp:.1f}")

        if state.rncan and state.rncan.zones:
            z = state.rncan.zones.get("auroral") or state.rncan.zones.get("polar")
            if z and z.next_6h:
                lvl = z.next_6h
                short_map = {
                    "quiet": "QUIET",
                    "unsettled": "UNSET",
                    "active": "ACT",
                    "stormy": "⚠️STORM",
                }
                short = short_map.get(lvl, lvl[:3].upper())
                parts.append(short)

        return " ".join(parts) if parts else "—"

    def _update_title(self, _):
        try:
            short = self._get_short_status()
            self.title = f"🌌 {short}"

            state = get_state()
            if state.last_fetch:
                try:
                    dt = datetime.fromisoformat(state.last_fetch.replace("Z", "+00:00"))
                    ts = dt.strftime("%H:%M")
                except Exception:
                    ts = "?"
                try:
                    self.menu["Last update: —"].title = f"Last update: {ts}"
                except Exception:
                    pass
        except Exception as e:
            log(f"Title update error: {e}")

    def open_dashboard(self, _):
        url = f"http://{WEB_HOST}:{WEB_PORT}"
        log(f"Opening dashboard: {url}")
        webbrowser.open(url)

    def refresh_now(self, _):
        try:
            rumps.notification(
                title="AurorA",
                subtitle="Fetching latest data…",
                message="",
                sound=False,
            )
            force_refresh()
            self._update_title(None)
            rumps.notification(
                title="AurorA",
                subtitle="Data refreshed",
                message="",
                sound=False,
            )
        except Exception as e:
            log(f"Refresh error: {e}")
            rumps.alert(f"Refresh failed: {e}")

    def quit_app(self, _):
        log("Quit requested from menu bar")
        rumps.quit_application()


def _show_startup_message(app):
    """Show a friendly notification only the very first time the user ever launches AurorA.
    Subsequent launches (even after reboot) will be silent. The menu bar icon itself is the indicator.
    """
    WELCOME_FLAG = Path.home() / ".aurora" / ".welcome_shown"
    try:
        if WELCOME_FLAG.exists():
            return  # already welcomed once in the lifetime of this app on this machine

        state = get_state()
        if state.latest_kp or (state.rncan and state.rncan.zones):
            rumps.notification(
                title="AurorA",
                subtitle="Prêt dans la barre de menu",
                message=f"Kp {state.latest_kp.kp:.1f}  •  Cliquez l’icône 🌌 pour le dashboard",
                sound=False,
            )
            WELCOME_FLAG.parent.mkdir(parents=True, exist_ok=True)
            WELCOME_FLAG.touch()
    except Exception:
        pass


def main():
    is_frozen = getattr(sys, "frozen", False) or hasattr(sys, "_MEIPASS")

    if rumps is None or sys.platform != "darwin":
        msg = "AurorA: rumps not installed or not running on macOS."
        log(msg)
        print(msg)
        print("→ Falling back to web dashboard only.")
        print(f"   Open http://{WEB_HOST}:{WEB_PORT} in your browser.")
        _show_fallback_notification(
            "AurorA",
            "Menu bar unavailable. Web dashboard is starting."
        )

        from aurora.scheduler import start_scheduler as _ss
        from aurora.web.server import run_server
        _ss()
        run_server()
        return

    log(f"Starting AurorA v{VERSION} (frozen={is_frozen})")
    try:
        app = AurorAMenuBar()
        app.run()
    except Exception as e:
        log("FATAL error in menubar app:")
        log(traceback.format_exc())
        _show_fallback_notification("AurorA crashed", str(e))
        # As last resort, still try to give the user the web UI
        try:
            from aurora.scheduler import start_scheduler as _ss
            from aurora.web.server import run_server
            _ss()
            run_server()
        except Exception:
            pass


if __name__ == "__main__":
    main()
