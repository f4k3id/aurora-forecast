#!/bin/zsh
#
# AurorA - Build a real macOS .app (menu bar only)
#
# This script:
#   - Finds or uses a good Python (prefers 3.11+)
#   - Creates a clean build venv
#   - Installs py2app + rumps + lean runtime deps (Flask stack, no lxml/fastapi/uvicorn/pydantic)
#   - Generates a simple aurora icon
#   - Builds dist/AurorA.app (much smaller than before)
#
# After success: copy dist/AurorA.app to ~/Applications or /Applications
#

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo "🌌 AurorA .app Builder"
echo "======================"

# Try to find a good Python (Homebrew, python.org, or system with 3.11+)
PYTHON=""
for candidate in \
    "/opt/homebrew/bin/python3" \
    "/usr/local/bin/python3" \
    "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3" \
    "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3" \
    "python3.12" \
    "python3.11" \
    "python3"
do
    if command -v "$candidate" >/dev/null 2>&1; then
        PY_VER=$("$candidate" --version 2>&1 | awk '{print $2}')
        MAJOR=$(echo "$PY_VER" | cut -d. -f1)
        MINOR=$(echo "$PY_VER" | cut -d. -f2)
        if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 10 ]; then
            PYTHON="$candidate"
            echo "Using Python: $PYTHON ($PY_VER)"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "❌ No suitable Python (>= 3.10) found."
    echo "Please install Python 3.11 or 3.12 from https://www.python.org or with Homebrew:"
    echo "    brew install python@3.12"
    exit 1
fi

# Clean previous build artifacts
echo "→ Cleaning previous builds..."
rm -rf build dist __pycache__ aurora/__pycache__ 2>/dev/null || true

# Create dedicated build venv
BUILD_VENV="$PROJECT_DIR/.build-venv"
echo "→ Creating clean build virtualenv at $BUILD_VENV"
rm -rf "$BUILD_VENV"
"$PYTHON" -m venv "$BUILD_VENV"
source "$BUILD_VENV/bin/activate"

echo "→ Upgrading pip..."
pip install --upgrade pip wheel setuptools 2>&1 | tail -3

# Install build tools FIRST (py2app + pillow needed for icon generation)
echo "→ Installing build tools (py2app + pillow)..."
pip install py2app pillow 2>&1 | tail -5

# Generate icon now that Pillow is guaranteed to be present
ICON_DIR="$PROJECT_DIR/icons"
mkdir -p "$ICON_DIR"

echo "→ Generating app icon..."
"$BUILD_VENV/bin/python" << 'PYEOF'
from PIL import Image, ImageDraw
import math
import random
from pathlib import Path

# Compute icon dir relative to CWD (the script cds to project root)
icon_dir = Path("icons")
icon_dir.mkdir(parents=True, exist_ok=True)

size = 1024
img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Deep night sky gradient
for y in range(size):
    t = y / size
    r = int(10 + 15 * (1-t))
    g = int(15 + 25 * (1-t))
    b = int(35 + 40 * (1-t))
    draw.line([(0, y), (size, y)], fill=(r, g, b, 255))

# Aurora waves (green-cyan-purple)
def aurora_wave(draw, base_y, amplitude, wavelength, color, thickness=18):
    points = []
    for x in range(0, size+10, 8):
        y = base_y + math.sin(x / wavelength) * amplitude
        y += math.sin(x / (wavelength*0.6)) * (amplitude*0.4)
        points.append((x, y))
    for i in range(thickness, 0, -2):
        alpha = int(40 + (thickness-i) * 12)
        glow_color = (*color[:3], alpha)
        for j in range(len(points)-1):
            draw.line([points[j], points[j+1]], fill=glow_color, width=i)

aurora_wave(draw, 420, 120, 280, (80, 255, 170, 255), 26)
aurora_wave(draw, 480, 95,  190, (90, 230, 255, 255), 20)
aurora_wave(draw, 550, 140, 340, (160, 120, 255, 255), 24)

# Stars
random.seed(42)
for _ in range(180):
    x = random.randint(0, size)
    y = random.randint(0, int(size*0.65))
    s = random.choice([1,1,1,2,2,3])
    a = random.randint(120, 255)
    draw.ellipse([x, y, x+s, y+s], fill=(255,255,255,a))

# Subtle lens flare
cx, cy = size//2, size//2 + 80
for i in range(6, 0, -1):
    alpha = 18 * i
    draw.ellipse([cx-180-i*8, cy-140-i*6, cx+180+i*8, cy+140+i*6],
                 outline=(120, 200, 255, alpha), width=2)

img.save(icon_dir / "AurorA.png", "PNG")
print(f"Icon generated: {icon_dir / 'AurorA.png'}")
PYEOF

# Copy icon to project root (referenced in setup.py as "AurorA.png")
cp "$ICON_DIR/AurorA.png" AurorA.png || true

# Now install the runtime dependencies — lean set only (Flask instead of FastAPI+uvicorn+lxml+pydantic)
echo "→ Installing runtime dependencies (rumps + flask stack)..."
pip install rumps flask requests beautifulsoup4 2>&1 | tail -8

echo "→ Building AurorA.app with py2app (this can take 30-90 seconds)..."
"$BUILD_VENV/bin/python" setup.py py2app 2>&1 | tail -20

if [ -d "dist/AurorA.app" ]; then
    echo ""
    echo "✅ SUCCESS!"
    echo "────────────────────────────────────────"
    echo "Your app is ready: dist/AurorA.app"
    echo ""
    echo "To install:"
    echo "    cp -R dist/AurorA.app ~/Applications/"
    echo "    # or"
    echo "    cp -R dist/AurorA.app /Applications/"
    echo ""
    echo "Then launch it from Spotlight or double-click."
    echo "It will appear in the menu bar (top right) with a 🌌 icon."
    echo ""
    echo "To remove from menu bar: right-click the icon → Quit AurorA"
    echo "────────────────────────────────────────"
else
    echo "❌ Build failed. Check the output above."
    exit 1
fi
