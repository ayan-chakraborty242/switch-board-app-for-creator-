#!/bin/bash
# Switchboard — Creator Dashboard
# Run this script to start the app

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check Python
if ! command -v python3 &>/dev/null; then
  echo "Error: python3 is required"
  exit 1
fi

# Install dependencies if needed
if ! python3 -c "import fastapi" 2>/dev/null; then
  echo "Installing dependencies..."
  pip install -r requirements.txt --break-system-packages -q
fi

# Check for ffmpeg (needed for frame extraction)
if ! command -v ffmpeg &>/dev/null; then
  echo "Warning: ffmpeg not found — frame extraction from video will not work"
  echo "Install with: sudo apt install ffmpeg  (or brew install ffmpeg on macOS)"
fi

# Get local IP for mobile access
LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || ipconfig getifaddr en0 2>/dev/null || echo "localhost")

echo ""
echo "╔════════════════════════════════════════╗"
echo "║       Switchboard Creator Dashboard    ║"
echo "╠════════════════════════════════════════╣"
echo "║  Local:   http://localhost:8000        ║"
echo "║  Mobile:  http://$LOCAL_IP:8000       ║"
echo "╚════════════════════════════════════════╝"
echo ""

python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
