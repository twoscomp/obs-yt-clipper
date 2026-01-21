#!/bin/bash
# OBS YouTube Clip Uploader - Installation Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$HOME/.config/obs-yt-clipper"
DATA_DIR="$HOME/.local/share/obs-yt-clipper"
INSTALL_DIR="$HOME/obs-yt-clipper"

echo "=== OBS YouTube Clip Uploader - Installation ==="
echo

# Check dependencies
echo "Checking dependencies..."

if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 is required but not installed."
    exit 1
fi

if ! command -v pip3 &> /dev/null && ! command -v pip &> /dev/null; then
    echo "ERROR: pip is required but not installed."
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

# Create directories
echo "Creating directories..."
mkdir -p "$CONFIG_DIR"
mkdir -p "$DATA_DIR"
mkdir -p "$INSTALL_DIR"

# Copy files
echo "Copying files..."
cp "$SCRIPT_DIR/upload_clip.py" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/auth_setup.py" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/obs_clip_hook.py" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/requirements.txt" "$INSTALL_DIR/"

# Copy config example if config doesn't exist
if [ ! -f "$CONFIG_DIR/config.yaml" ]; then
    cp "$SCRIPT_DIR/config.yaml.example" "$CONFIG_DIR/config.yaml"
    echo "Created config file at $CONFIG_DIR/config.yaml"
fi

# Make scripts executable
chmod +x "$INSTALL_DIR/upload_clip.py"
chmod +x "$INSTALL_DIR/auth_setup.py"

# Install Python dependencies
echo
echo "Installing Python dependencies..."
pip3 install --user -r "$INSTALL_DIR/requirements.txt"

echo
echo "=== Installation Complete ==="
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
echo "   python3 $INSTALL_DIR/auth_setup.py"
echo
echo "3. Add the OBS script:"
echo "   a. Open OBS Studio"
echo "   b. Go to Tools > Scripts"
echo "   c. Click '+' and add: $INSTALL_DIR/obs_clip_hook.py"
echo "   d. Configure the 'Upload Script Path' to: $INSTALL_DIR/upload_clip.py"
echo
echo "4. Test by saving a replay buffer clip!"
echo
