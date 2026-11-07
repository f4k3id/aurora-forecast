#!/usr/bin/env python3
"""
Standalone launcher: starts scheduler + web dashboard (no menubar).
Useful on any OS or when rumps cannot be installed.
"""
from aurora.scheduler import start_scheduler
from aurora.web.server import run_server

if __name__ == "__main__":
    print("Starting AurorA scheduler + web UI (no menubar)...")
    start_scheduler()
    run_server()
