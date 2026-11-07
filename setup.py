"""
py2app setup for AurorA
Builds a proper macOS .app that lives only in the menu bar.

Usage:
    python setup.py py2app

After build: dist/AurorA.app  → copy to /Applications
"""

from setuptools import setup

APP = ["menubar.py"]
DATA_FILES = []

OPTIONS = {
    "py2app": {
        # The main script that will be the app
        "argv_emulation": False,
        # Make it a pure menu bar / agent app (no Dock icon)
        "plist": {
            "CFBundleName": "AurorA",
            "CFBundleDisplayName": "AurorA",
            "CFBundleIdentifier": "com.user.aurora",
            "CFBundleVersion": "0.2.0",
            "CFBundleShortVersionString": "0.2.0",
            "NSPrincipalClass": "NSApplication",
            "LSUIElement": True,                    # ← Critical: only menu bar, no Dock
            "LSMinimumSystemVersion": "11.0",
            "NSHumanReadableCopyright": "© 2026",
            # Optional: you can add more keys later
        },
        # Packages that must be included explicitly sometimes.
        # We use a very small set now (Flask instead of FastAPI+uvicorn) to keep the .app tiny.
        "packages": [
            "aurora",
            "flask",
            "werkzeug",
            "jinja2",   # Flask pulls it even if we don't use Jinja templates (the dashboard is one big string)
            "rumps",
            "requests",
            "bs4",
            "soupsieve",
            # apscheduler intentionally omitted — we use a tiny pure-threading scheduler
        ],
        # Include everything from aurora package.
        "includes": [
            "aurora.web.server",
            "aurora.fetcher",
            "aurora.scheduler",
            "aurora.store",
            "aurora.notifier",
            "aurora.config",
            "aurora.models",
        ],
        # Aggressive excludes — these are the main things that used to bloat the bundle.
        "excludes": [
            "tkinter", "test", "unittest",
            "PyQt5", "PyQt6", "matplotlib", "numpy", "pandas",
            "lxml",
            "pydantic", "pydantic_core",
            "fastapi", "starlette", "uvicorn", "uvloop", "httptools", "watchfiles",
            "websockets", "anyio", "h11", "httpcore",
            "pyyaml", "yaml",
            "cryptography",
        ],
        "semi_standalone": True,
        "iconfile": "AurorA.png",
    }
}

setup(
    name="AurorA",
    app=APP,
    data_files=DATA_FILES,
    options=OPTIONS,
    setup_requires=["py2app"],
)