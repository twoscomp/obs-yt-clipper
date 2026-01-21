# OBS YouTube Clip Uploader

Automatically upload OBS replay buffer clips to YouTube with minimal friction.

When you save a replay buffer clip in OBS, this tool:
1. Detects what game you're playing (via active window)
2. Renames the clip to `{Game} - {Timestamp}.mp4`
3. Uploads it to YouTube as unlisted
4. Sends a desktop notification with the YouTube link

## Requirements

- Linux (tested on Fedora/Bazzite/Ubuntu)
- OBS Studio with replay buffer enabled
- Python 3.8+
- `xdotool` (for game detection)
- `notify-send` (for desktop notifications)

## Quick Start

### 1. Clone and Run Setup

```bash
git clone https://github.com/yourusername/obs-yt-clipper.git
cd obs-yt-clipper
./setup.sh
```

The setup script will:
- Check system dependencies
- Create a Python virtual environment
- Install Python dependencies
- Print the exact paths you need for OBS configuration

### 2. Install System Dependencies

**Fedora/Bazzite:**
```bash
sudo dnf install xdotool libnotify
```

**Ubuntu/Debian:**
```bash
sudo apt install xdotool libnotify-bin
```

### 3. Set Up YouTube API Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)
3. Navigate to **APIs & Services > Library**
4. Search for and enable **YouTube Data API v3**
5. Go to **APIs & Services > Credentials**
6. Click **Create Credentials > OAuth client ID**
7. If prompted, configure the OAuth consent screen:
   - Choose "External" user type
   - Fill in app name, user support email, developer email
   - Skip scopes, add yourself as a test user
8. Back in Credentials, create OAuth client ID:
   - Select **Desktop app** as the application type
   - Name it "OBS Clip Uploader"
9. Download the JSON file
10. Save it as `~/.config/obs-yt-clipper/credentials.json`:

```bash
mv ~/Downloads/client_secret_*.json ~/.config/obs-yt-clipper/credentials.json
```

### 4. Authenticate

Run the authentication setup (the exact command is shown by `./setup.sh`):

```bash
/path/to/repo/.venv/bin/python /path/to/repo/auth_setup.py
```

This opens a browser window to authorize the app. After authorization, a refresh token is saved locally.

### 5. Configure OBS

1. Open OBS Studio
2. Go to **Tools > Scripts**
3. Click the **+** button
4. Add `obs_clip_hook.py` from your repo directory
5. In the script settings, paste the paths from `./setup.sh` output:
   - **Upload Script Path**: `/path/to/repo/upload_clip.py`
   - **Python Executable**: `/path/to/repo/.venv/bin/python`

### 6. Enable Replay Buffer

1. In OBS, go to **Settings > Output > Replay Buffer**
2. Enable replay buffer
3. Set your desired replay duration
4. Configure the output path (e.g., `~/Videos/Replays`)

## Flatpak OBS Setup (Bazzite/Fedora Atomic)

If you're using OBS as a Flatpak (common on Bazzite and Fedora Atomic desktops), additional permissions are required for game detection to work.

### Grant Flatpak Permissions

The OBS Flatpak needs permission to spawn commands on the host system for `xdotool` to detect the active window:

```bash
flatpak override --user --talk-name=org.freedesktop.Flatpak com.obsproject.Studio
```

### Restart OBS

After granting permissions, fully restart OBS for changes to take effect.

### How It Works

When running inside a Flatpak sandbox, the script automatically uses `flatpak-spawn --host` to run `xdotool` on the host system, bypassing the sandbox restrictions.

### Wayland Note

On Wayland, `xdotool` can only detect windows running through XWayland. Most games (especially those running via Proton/Wine) use XWayland and will be detected correctly. Native Wayland applications may not be detected.

## Usage

1. Start OBS with replay buffer enabled
2. Play your game
3. When something cool happens, press your replay buffer hotkey
4. The clip is automatically uploaded to YouTube
5. A desktop notification appears with the YouTube link

## Configuration

Edit `~/.config/obs-yt-clipper/config.yaml`:

```yaml
youtube:
  privacy: unlisted  # public, unlisted, or private
  description_template: "Recorded on {date}"

retry:
  max_attempts: 3
  backoff_seconds: 30
```

## Adding Custom Game Names

The script includes a mapping of common games. To add your own, edit `obs_clip_hook.py` and add entries to `GAME_NAME_MAP`:

```python
GAME_NAME_MAP = {
    # ... existing entries ...
    "yourgame": "Your Game Name",
    "yourgame.exe": "Your Game Name",
}
```

## Troubleshooting

### Check upload logs

```bash
cat ~/.local/share/obs-yt-clipper/uploads.log
```

### Test upload manually

```bash
/path/to/repo/.venv/bin/python /path/to/repo/upload_clip.py \
  --file "/path/to/test/video.mp4" \
  --title "Test Upload"
```

### Game not detected correctly

1. Check OBS Script Log (**Tools > Scripts > Script Log**) for debug output
2. Verify `xdotool` is installed on the host system
3. For Flatpak OBS, ensure permissions are granted (see above)
4. Test xdotool manually: `xdotool getactivewindow getwindowname`

### Token expired

If uploads fail with authentication errors, re-run the auth setup:

```bash
/path/to/repo/.venv/bin/python /path/to/repo/auth_setup.py
```

### OBS script not running

1. Check OBS script log: **Tools > Scripts > Script Log**
2. Ensure the Python executable path points to your virtual environment's python
3. Verify the upload script path is correct

### No notifications

1. Ensure `notify-send` is installed on the host system (not in a container)
2. Check that Do Not Disturb is disabled
3. Verify your desktop environment supports freedesktop notifications

## File Structure

```
~/.config/obs-yt-clipper/
├── config.yaml         # Configuration
├── credentials.json    # OAuth credentials (from Google Cloud)
└── token.json          # Refresh token (created by auth_setup.py)

~/.local/share/obs-yt-clipper/
└── uploads.log         # Upload history and errors

/path/to/obs-yt-clipper/   # Your cloned repo
├── .venv/                 # Python virtual environment (created by setup.sh)
├── obs_clip_hook.py       # OBS script
├── upload_clip.py         # Upload script
├── auth_setup.py          # OAuth setup
├── requirements.txt       # Python dependencies
├── setup.sh               # Setup script
└── README.md              # This file
```

## Running Tests

```bash
source .venv/bin/activate
pip install -r requirements-test.txt
pytest tests/ -v
```

## License

MIT
