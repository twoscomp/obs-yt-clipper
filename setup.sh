#!/bin/bash
# OBS YouTube Clip Uploader - Setup Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$HOME/.config/obs-yt-clipper"
DATA_DIR="$HOME/.local/share/obs-yt-clipper"
VENV_DIR="$SCRIPT_DIR/.venv"

echo "=== OBS YouTube Clip Uploader - Setup ==="
echo

# Check dependencies
echo "Checking dependencies..."

if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 is required but not installed."
    exit 1
fi

if ! command -v xdotool &> /dev/null; then
    echo "WARNING: xdotool is not installed. Game detection may not work."
    echo "Install with: sudo dnf install xdotool (Fedora) or sudo apt install xdotool (Ubuntu)"
fi

if ! command -v notify-send &> /dev/null; then
    echo "WARNING: notify-send is not installed. Desktop notifications will not work."
    echo "Install with: sudo dnf install libnotify (Fedora) or sudo apt install libnotify-bin (Ubuntu)"
fi

echo "Dependencies OK"
echo

# Create config directories
echo "Creating directories..."
mkdir -p "$CONFIG_DIR"
mkdir -p "$DATA_DIR"

# Copy config example if config doesn't exist
if [ ! -f "$CONFIG_DIR/config.yaml" ]; then
    cp "$SCRIPT_DIR/config.yaml.example" "$CONFIG_DIR/config.yaml"
    echo "Created config file at $CONFIG_DIR/config.yaml"
fi

# Create virtual environment
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

echo "Installing Python dependencies..."
"$VENV_DIR/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"

echo
echo "=== Setup Complete ==="
echo
echo "Next steps:"
echo
echo "1. Set up YouTube API credentials:"
echo "   a. Go to https://console.cloud.google.com/"
echo "   b. Create a project and enable 'YouTube Data API v3'"
echo "   c. Create OAuth 2.0 credentials (Desktop app type)"
echo "   d. Download the JSON and save as: $CONFIG_DIR/credentials.json"
echo
echo "2. Run the authentication setup:"
echo "   $VENV_DIR/bin/python $SCRIPT_DIR/auth_setup.py"
echo
echo "3. Add the OBS script:"
echo "   a. Open OBS Studio"
echo "   b. Go to Tools > Scripts"
echo "   c. Click '+' and add: $SCRIPT_DIR/obs_clip_hook.py"
echo
echo "4. Configure the OBS script settings (COPY THESE PATHS):"
echo "   Upload Script Path: $SCRIPT_DIR/upload_clip.py"
echo "   Python Executable:  $VENV_DIR/bin/python"
echo
echo "5. Test by saving a replay buffer clip!"
