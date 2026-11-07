from __future__ import annotations
import subprocess
import sys
from typing import Optional

from .config import APP_NAME


def send_macos_notification(title: str, message: str, subtitle: Optional[str] = None) -> bool:
    """
    Send a native macOS notification using osascript.
    Falls back silently on non-macOS.
    """
    if sys.platform != "darwin":
        print(f"[notify] (non-mac) {title}: {message}")
        return False

    try:
        # Build AppleScript
        parts = [f'display notification "{message}"']
        if subtitle:
            parts.append(f'with title "{title}" subtitle "{subtitle}"')
        else:
            parts.append(f'with title "{title}"')

        script = " ".join(parts)
        subprocess.run(
            ["osascript", "-e", script],
            check=False,
            capture_output=True,
            timeout=5,
        )
        return True
    except Exception as e:
        print(f"[notify] error: {e}")
        return False


def notify_stormy(zone: str, level: str, kp: Optional[float] = None, lang: str = "en"):
    """High priority alert when we detect Stormy."""
    if lang == "fr":
        title = "🌌 Aurores Boréales - ALERTE ORAGEUSE"
        msg = f"Activité {level.upper()} détectée pour la zone {zone}."
        if kp is not None:
            msg += f" (Kp {kp})"
        sub = "Conditions favorables aux aurores à basses latitudes"
    else:
        title = "🌌 Aurora Alert - STORMY"
        msg = f"{level.upper()} activity detected for {zone} zone."
        if kp is not None:
            msg += f" (Kp {kp})"
        sub = "Good conditions possible at lower latitudes"

    send_macos_notification(title, msg, subtitle=sub)
