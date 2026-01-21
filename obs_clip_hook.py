"""
OBS Python Script: Automatically upload replay buffer clips to YouTube.

This script hooks into OBS's replay buffer save event, detects the active game,
renames the clip, and spawns upload_clip.py as a detached subprocess.

To install:
1. Copy this file to your OBS scripts folder or add it via Tools > Scripts
2. Configure the upload script path in the script settings
"""

import os
import subprocess
import re
from datetime import datetime
from pathlib import Path

import obspython as obs

# Script settings (configured via OBS UI)
upload_script_path = ""
python_executable = "python3"

# Known game process name mappings (extend as needed)
GAME_NAME_MAP = {
    "valorant": "Valorant",
    "valorant.exe": "Valorant",
    "csgo": "CS:GO",
    "cs2": "Counter-Strike 2",
    "overwatch": "Overwatch",
    "leagueoflegends": "League of Legends",
    "league of legends": "League of Legends",
    "riotclientux": "League of Legends",
    "dota2": "Dota 2",
    "minecraft": "Minecraft",
    "fortnite": "Fortnite",
    "apex": "Apex Legends",
    "r5apex": "Apex Legends",
    "rocketleague": "Rocket League",
    "gta5": "GTA V",
    "gtav": "GTA V",
    "elden ring": "Elden Ring",
    "eldenring": "Elden Ring",
    "arc raiders": "Arc Raiders",
    "arcraiders": "Arc Raiders",
    "steam": "Steam Game",
    "lutris": "Game",
}


def script_description():
    return """<h2>OBS YouTube Clip Uploader</h2>
    <p>Automatically uploads replay buffer clips to YouTube.</p>
    <p>Detects the active game and names clips accordingly.</p>
    """


def script_properties():
    props = obs.obs_properties_create()

    obs.obs_properties_add_path(
        props,
        "upload_script_path",
        "Upload Script Path",
        obs.OBS_PATH_FILE,
        "Python files (*.py)",
        str(Path.home() / "obs-yt-clipper"),
    )

    obs.obs_properties_add_text(
        props,
        "python_executable",
        "Python Executable",
        obs.OBS_TEXT_DEFAULT,
    )

    return props


def script_defaults(settings):
    obs.obs_data_set_default_string(
        settings,
        "upload_script_path",
        str(Path.home() / "obs-yt-clipper" / "upload_clip.py"),
    )
    obs.obs_data_set_default_string(settings, "python_executable", "python3")


def script_update(settings):
    global upload_script_path, python_executable
    upload_script_path = obs.obs_data_get_string(settings, "upload_script_path")
    python_executable = obs.obs_data_get_string(settings, "python_executable")


def script_load(settings):
    obs.obs_frontend_add_event_callback(on_frontend_event)
    obs.script_log(obs.LOG_INFO, "OBS YouTube Clip Uploader loaded")


def script_unload():
    obs.script_log(obs.LOG_INFO, "OBS YouTube Clip Uploader unloaded")


def on_frontend_event(event):
    if event == obs.OBS_FRONTEND_EVENT_REPLAY_BUFFER_SAVED:
        handle_replay_saved()


def _run_host_command(cmd: list) -> subprocess.CompletedProcess:
    """Run a command, using flatpak-spawn if inside a Flatpak sandbox."""
    env = os.environ.copy()
    if "DISPLAY" not in env:
        env["DISPLAY"] = ":0"

    # Check if we're inside a Flatpak
    if os.path.exists("/.flatpak-info"):
        cmd = ["flatpak-spawn", "--host"] + cmd

    return subprocess.run(cmd, capture_output=True, text=True, timeout=2, env=env)


def play_audio_cue():
    """Play a notification sound when clip is saved."""
    script_dir = Path(__file__).parent
    audio_file = script_dir / "sounds" / "clip_saved.wav"

    if not audio_file.exists():
        obs.script_log(obs.LOG_DEBUG, f"Audio cue file not found: {audio_file}")
        return

    try:
        _run_host_command(["paplay", str(audio_file)])
    except Exception as e:
        obs.script_log(obs.LOG_DEBUG, f"Could not play audio cue: {e}")


def get_active_window_name() -> str:
    """Get the name of the active window using xdotool."""
    try:
        result = _run_host_command(["xdotool", "getactivewindow", "getwindowname"])
        if result.returncode == 0:
            name = result.stdout.strip()
            # Remove zero-width and invisible unicode characters
            name = re.sub(r'[\u200b-\u200f\u2028-\u202f\u2060-\u206f\ufeff]', '', name)
            return name
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return ""


def get_active_window_class() -> str:
    """Get the process name of the active window using xdotool."""
    try:
        result = _run_host_command(["xdotool", "getactivewindow", "getwindowpid"])
        if result.returncode == 0:
            pid = result.stdout.strip()
            # Get process name from /proc (accessible even in Flatpak with --filesystem=host)
            try:
                with open(f"/proc/{pid}/comm") as f:
                    return f.read().strip()
            except (FileNotFoundError, PermissionError):
                pass
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return ""


def detect_game_name() -> str:
    """Detect the active game from window name or class."""
    window_name = get_active_window_name()
    window_class = get_active_window_class()

    obs.script_log(obs.LOG_DEBUG, f"Active window: '{window_name}' ({window_class})")

    # Check window class first (more reliable)
    class_lower = window_class.lower()
    for pattern, game_name in GAME_NAME_MAP.items():
        if pattern in class_lower:
            return game_name

    # Check window name
    name_lower = window_name.lower()
    for pattern, game_name in GAME_NAME_MAP.items():
        if pattern in name_lower:
            return game_name

    # If window name looks like a game title, use it directly
    if window_name and not any(x in window_name.lower() for x in ["obs", "chrome", "firefox", "terminal", "code"]):
        # Clean up window name (remove version numbers, etc.)
        clean_name = re.sub(r"\s*[-–]\s*.*$", "", window_name)  # Remove " - subtitle" parts
        clean_name = re.sub(r"\s*\(.*?\)\s*", " ", clean_name)  # Remove (stuff in parens)
        clean_name = re.sub(r"\s*v?\d+\.\d+.*$", "", clean_name)  # Remove version numbers
        clean_name = clean_name.strip()
        if clean_name and len(clean_name) < 50:
            return clean_name

    return "Clip"


def get_replay_path() -> str:
    """Get the path of the last saved replay from OBS output settings."""
    output = obs.obs_frontend_get_replay_buffer_output()
    if output:
        settings = obs.obs_output_get_settings(output)
        path = obs.obs_data_get_string(settings, "path")
        obs.obs_data_release(settings)
        obs.obs_output_release(output)
        return path
    return ""


def find_latest_replay(directory: str) -> str:
    """Find the most recently created replay file in the directory."""
    replay_dir = Path(directory)
    if not replay_dir.exists():
        return ""

    # Find most recent .mp4 or .mkv file
    video_files = list(replay_dir.glob("*.mp4")) + list(replay_dir.glob("*.mkv"))
    if not video_files:
        return ""

    latest = max(video_files, key=lambda p: p.stat().st_mtime)
    return str(latest)


def handle_replay_saved():
    """Handle replay buffer save event."""
    global upload_script_path, python_executable

    play_audio_cue()

    if not upload_script_path or not os.path.exists(upload_script_path):
        obs.script_log(obs.LOG_WARNING, f"Upload script not found: {upload_script_path}")
        return

    # Get replay directory from OBS settings
    replay_path = get_replay_path()
    if not replay_path:
        # Fall back to common locations
        for fallback in ["~/Videos/Replays", "~/Videos", "~/OBS"]:
            expanded = os.path.expanduser(fallback)
            if os.path.isdir(expanded):
                replay_path = expanded
                break

    if not replay_path:
        obs.script_log(obs.LOG_WARNING, "Could not determine replay directory")
        return

    # Find the most recent replay file
    original_file = find_latest_replay(replay_path)
    if not original_file:
        obs.script_log(obs.LOG_WARNING, f"No replay file found in {replay_path}")
        return

    obs.script_log(obs.LOG_INFO, f"Replay saved: {original_file}")

    # Detect game and format timestamp
    game_name = detect_game_name()
    timestamp = datetime.now()
    formatted_time = timestamp.strftime("%Y-%m-%d %H-%M")
    title = f"{game_name} - {timestamp.strftime('%Y-%m-%d %H:%M')}"

    # Rename file
    original_path = Path(original_file)
    new_filename = f"{game_name} - {formatted_time}{original_path.suffix}"
    new_path = original_path.parent / new_filename

    try:
        if original_path != new_path and not new_path.exists():
            original_path.rename(new_path)
            obs.script_log(obs.LOG_INFO, f"Renamed to: {new_filename}")
            file_to_upload = str(new_path)
        else:
            file_to_upload = original_file
    except OSError as e:
        obs.script_log(obs.LOG_WARNING, f"Could not rename file: {e}")
        file_to_upload = original_file

    # Spawn upload subprocess (detached)
    try:
        subprocess.Popen(
            [python_executable, upload_script_path, "--file", file_to_upload, "--title", title],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        obs.script_log(obs.LOG_INFO, f"Upload started: {title}")
    except Exception as e:
        obs.script_log(obs.LOG_ERROR, f"Failed to start upload: {e}")
