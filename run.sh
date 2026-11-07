#!/bin/zsh
# Quick launcher for AurorA
cd "$(dirname "$0")"
source .venv/bin/activate 2>/dev/null || true
python menubar.py
