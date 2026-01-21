#!/usr/bin/env python3
"""
Upload a video clip to YouTube with retry logic and desktop notifications.
Designed to be spawned as a subprocess by obs_clip_hook.py.
"""

import argparse
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "obs-yt-clipper" / "config.yaml"

def load_config(config_path: Path) -> dict:
    """Load configuration from YAML file."""
    if not config_path.exists():
        return {
            "youtube": {
                "privacy": "unlisted",
                "description_template": "Recorded on {date}",
            },
            "credentials_path": str(Path.home() / ".config" / "obs-yt-clipper" / "credentials.json"),
            "token_path": str(Path.home() / ".config" / "obs-yt-clipper" / "token.json"),
            "log_path": str(Path.home() / ".local" / "share" / "obs-yt-clipper" / "uploads.log"),
            "retry": {
                "max_attempts": 3,
                "backoff_seconds": 30,
            },
        }

    with open(config_path) as f:
        return yaml.safe_load(f)


def setup_logging(log_path: str) -> logging.Logger:
    """Set up logging to file and stderr."""
    log_file = Path(log_path)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("upload_clip")
    logger.setLevel(logging.DEBUG)

    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    )

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.INFO)
    stderr_handler.setFormatter(
        logging.Formatter("%(levelname)s: %(message)s")
    )

    logger.addHandler(file_handler)
    logger.addHandler(stderr_handler)

    return logger


def send_notification(title: str, message: str, urgency: str = "normal") -> None:
    """Send a desktop notification using notify-send."""
    try:
        subprocess.run(
            ["notify-send", "-u", urgency, "-a", "OBS Clip Uploader", title, message],
            check=False,
            capture_output=True,
        )
    except FileNotFoundError:
        pass  # notify-send not available


def copy_to_clipboard(text: str) -> bool:
    """Copy text to clipboard using wl-copy (Wayland) or xclip (X11)."""
    # Try wl-copy first (Wayland)
    try:
        subprocess.run(
            ["wl-copy", text],
            check=True,
            capture_output=True,
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    # Fall back to xclip (X11)
    try:
        subprocess.run(
            ["xclip", "-selection", "clipboard"],
            input=text.encode(),
            check=True,
            capture_output=True,
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    return False


def send_notification_with_actions(
    title: str,
    message: str,
    url: str,
    logger: logging.Logger,
) -> None:
    """Send a notification with Copy Link and Open in Browser actions."""
    try:
        # notify-send with actions blocks until user interacts or timeout
        result = subprocess.run(
            [
                "notify-send",
                "-u", "normal",
                "-a", "OBS Clip Uploader",
                "--action=copy=Copy Link",
                "--action=open=Open in Browser",
                title,
                message,
            ],
            capture_output=True,
            text=True,
            timeout=30,  # 30 second timeout
        )

        action = result.stdout.strip()

        if action == "copy":
            if copy_to_clipboard(url):
                logger.info(f"Copied URL to clipboard: {url}")
                send_notification("Link Copied!", url)
            else:
                logger.warning("Failed to copy to clipboard - no clipboard tool available")
                send_notification("Copy Failed", "Install wl-copy or xclip", "critical")

        elif action == "open":
            logger.info(f"Opening URL in browser: {url}")
            subprocess.Popen(
                ["xdg-open", url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    except subprocess.TimeoutExpired:
        logger.debug("Notification timed out without user interaction")
    except FileNotFoundError:
        # Fall back to basic notification
        logger.debug("notify-send with actions not available, using basic notification")
        send_notification(title, message)


def get_youtube_service(token_path: str, logger: logging.Logger):
    """Build YouTube API service using cached credentials."""
    token_file = Path(token_path)

    if not token_file.exists():
        logger.error(f"Token file not found: {token_path}")
        logger.error("Run auth_setup.py first to authenticate with YouTube.")
        raise FileNotFoundError(f"Token file not found: {token_path}")

    creds = Credentials.from_authorized_user_file(
        token_path,
        scopes=["https://www.googleapis.com/auth/youtube.upload"]
    )

    if creds.expired and creds.refresh_token:
        from google.auth.transport.requests import Request
        logger.info("Refreshing expired credentials...")
        creds.refresh(Request())
        with open(token_path, "w") as f:
            f.write(creds.to_json())

    return build("youtube", "v3", credentials=creds)


def upload_video(
    youtube,
    file_path: str,
    title: str,
    description: str,
    privacy: str,
    logger: logging.Logger,
) -> str:
    """Upload a video to YouTube and return the video ID."""
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": "20",  # Gaming category
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        file_path,
        mimetype="video/mp4",
        resumable=True,
        chunksize=1024 * 1024,  # 1MB chunks
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            logger.debug(f"Upload progress: {int(status.progress() * 100)}%")

    return response["id"]


def upload_with_retry(
    youtube,
    file_path: str,
    title: str,
    description: str,
    privacy: str,
    max_attempts: int,
    backoff_seconds: int,
    logger: logging.Logger,
) -> str:
    """Upload video with exponential backoff retry logic."""
    last_error = None

    for attempt in range(1, max_attempts + 1):
        try:
            logger.info(f"Upload attempt {attempt}/{max_attempts}")
            video_id = upload_video(youtube, file_path, title, description, privacy, logger)
            logger.info(f"Upload successful! Video ID: {video_id}")
            return video_id
        except HttpError as e:
            last_error = e
            if e.resp.status in [500, 502, 503, 504]:
                wait_time = backoff_seconds * (2 ** (attempt - 1))
                logger.warning(f"Server error ({e.resp.status}), retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                logger.error(f"HTTP error: {e}")
                raise
        except Exception as e:
            last_error = e
            wait_time = backoff_seconds * (2 ** (attempt - 1))
            logger.warning(f"Upload failed: {e}, retrying in {wait_time}s...")
            time.sleep(wait_time)

    logger.error(f"All {max_attempts} upload attempts failed")
    raise last_error


def main():
    parser = argparse.ArgumentParser(description="Upload a clip to YouTube")
    parser.add_argument("--file", required=True, help="Path to the video file")
    parser.add_argument("--title", required=True, help="Video title")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config file path")
    args = parser.parse_args()

    config = load_config(Path(args.config))
    logger = setup_logging(config["log_path"])

    file_path = os.path.expanduser(args.file)
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        send_notification("Upload Failed", f"File not found: {file_path}", "critical")
        sys.exit(1)

    logger.info(f"Starting upload: {args.title}")
    logger.debug(f"File: {file_path}")

    description = config["youtube"]["description_template"].format(
        date=datetime.now().strftime("%Y-%m-%d %H:%M")
    )

    try:
        youtube = get_youtube_service(config["token_path"], logger)

        video_id = upload_with_retry(
            youtube=youtube,
            file_path=file_path,
            title=args.title,
            description=description,
            privacy=config["youtube"]["privacy"],
            max_attempts=config["retry"]["max_attempts"],
            backoff_seconds=config["retry"]["backoff_seconds"],
            logger=logger,
        )

        video_url = f"https://youtu.be/{video_id}"
        logger.info(f"Video URL: {video_url}")
        send_notification_with_actions("Clip Uploaded!", video_url, video_url, logger)

    except FileNotFoundError as e:
        send_notification("Upload Failed", str(e), "critical")
        sys.exit(1)
    except Exception as e:
        logger.exception("Upload failed")
        send_notification("Upload Failed", str(e), "critical")
        sys.exit(1)


if __name__ == "__main__":
    main()
