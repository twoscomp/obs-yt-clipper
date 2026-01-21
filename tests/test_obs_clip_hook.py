"""Tests for obs_clip_hook.py.

Since obspython is only available inside OBS, we mock it for testing.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime

import pytest

# Create a mock obspython module before importing obs_clip_hook
mock_obs = MagicMock()
mock_obs.LOG_INFO = 0
mock_obs.LOG_WARNING = 1
mock_obs.LOG_ERROR = 2
mock_obs.LOG_DEBUG = 3
mock_obs.OBS_FRONTEND_EVENT_REPLAY_BUFFER_SAVED = 100
mock_obs.OBS_PATH_FILE = 1
mock_obs.OBS_TEXT_DEFAULT = 0
sys.modules["obspython"] = mock_obs

# Now we can import from obs_clip_hook
sys.path.insert(0, str(Path(__file__).parent.parent))

from obs_clip_hook import (
    GAME_NAME_MAP,
    get_active_window_name,
    get_active_window_class,
    detect_game_name,
    find_latest_replay,
    play_audio_cue,
)


class TestGameNameMap:
    """Tests for GAME_NAME_MAP configuration."""

    def test_game_name_map_contains_common_games(self):
        """Should have mappings for common games."""
        assert "valorant" in GAME_NAME_MAP
        assert "minecraft" in GAME_NAME_MAP
        assert "csgo" in GAME_NAME_MAP

    def test_game_name_map_values_are_formatted(self):
        """Game names should be properly formatted."""
        assert GAME_NAME_MAP["valorant"] == "Valorant"
        assert GAME_NAME_MAP["league of legends"] == "League of Legends"
        assert GAME_NAME_MAP["csgo"] == "CS:GO"


class TestGetActiveWindowName:
    """Tests for get_active_window_name function."""

    @patch("obs_clip_hook.subprocess.run")
    def test_get_active_window_name_returns_window_title(self, mock_run):
        """Should return the active window name from xdotool."""
        mock_run.return_value = MagicMock(returncode=0, stdout="Valorant\n")

        result = get_active_window_name()

        assert result == "Valorant"
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "xdotool" in args
        assert "getwindowname" in args

    @patch("obs_clip_hook.subprocess.run")
    def test_get_active_window_name_returns_empty_on_failure(self, mock_run):
        """Should return empty string when xdotool fails."""
        mock_run.return_value = MagicMock(returncode=1, stdout="")

        result = get_active_window_name()

        assert result == ""

    @patch("obs_clip_hook.subprocess.run", side_effect=FileNotFoundError)
    def test_get_active_window_name_handles_missing_xdotool(self, mock_run):
        """Should return empty string when xdotool is not installed."""
        result = get_active_window_name()

        assert result == ""

    @patch("obs_clip_hook.subprocess.run")
    def test_get_active_window_name_handles_timeout(self, mock_run):
        """Should return empty string on timeout."""
        from subprocess import TimeoutExpired

        mock_run.side_effect = TimeoutExpired("xdotool", 2)

        result = get_active_window_name()

        assert result == ""


class TestGetActiveWindowClass:
    """Tests for get_active_window_class function."""

    @patch("builtins.open", create=True)
    @patch("obs_clip_hook.subprocess.run")
    def test_get_active_window_class_returns_class_name(self, mock_run, mock_open):
        """Should return process name via PID from xdotool."""
        mock_run.return_value = MagicMock(returncode=0, stdout="12345\n")
        mock_file = MagicMock()
        mock_file.read.return_value = "VALORANT.exe\n"
        mock_file.__enter__ = MagicMock(return_value=mock_file)
        mock_file.__exit__ = MagicMock(return_value=False)
        mock_open.return_value = mock_file

        result = get_active_window_class()

        assert result == "VALORANT.exe"
        args = mock_run.call_args[0][0]
        assert "getwindowpid" in args


class TestDetectGameName:
    """Tests for detect_game_name function."""

    @patch("obs_clip_hook.get_active_window_class")
    @patch("obs_clip_hook.get_active_window_name")
    def test_detect_game_name_matches_from_class(self, mock_name, mock_class):
        """Should detect game from window class."""
        mock_name.return_value = "Some Window"
        mock_class.return_value = "valorant.exe"

        result = detect_game_name()

        assert result == "Valorant"

    @patch("obs_clip_hook.get_active_window_class")
    @patch("obs_clip_hook.get_active_window_name")
    def test_detect_game_name_matches_from_window_name(self, mock_name, mock_class):
        """Should detect game from window name when class doesn't match."""
        mock_name.return_value = "Minecraft 1.20"
        mock_class.return_value = "java"

        result = detect_game_name()

        assert result == "Minecraft"

    @patch("obs_clip_hook.get_active_window_class")
    @patch("obs_clip_hook.get_active_window_name")
    def test_detect_game_name_uses_window_title_as_fallback(self, mock_name, mock_class):
        """Should use cleaned window title when no match in map."""
        mock_name.return_value = "Awesome Game 2024 - Main Menu"
        mock_class.return_value = "unknown"

        result = detect_game_name()

        assert result == "Awesome Game 2024"

    @patch("obs_clip_hook.get_active_window_class")
    @patch("obs_clip_hook.get_active_window_name")
    def test_detect_game_name_filters_common_apps(self, mock_name, mock_class):
        """Should not use common app names as game names."""
        mock_name.return_value = "OBS Studio"
        mock_class.return_value = "obs"

        result = detect_game_name()

        assert result == "Clip"  # Default fallback

    @patch("obs_clip_hook.get_active_window_class")
    @patch("obs_clip_hook.get_active_window_name")
    def test_detect_game_name_returns_clip_when_no_window(self, mock_name, mock_class):
        """Should return 'Clip' when no window is detected."""
        mock_name.return_value = ""
        mock_class.return_value = ""

        result = detect_game_name()

        assert result == "Clip"

    @patch("obs_clip_hook.get_active_window_class")
    @patch("obs_clip_hook.get_active_window_name")
    def test_detect_game_name_cleans_version_numbers(self, mock_name, mock_class):
        """Should remove version numbers from window titles."""
        mock_name.return_value = "Cool Game v1.2.3"
        mock_class.return_value = "unknown"

        result = detect_game_name()

        assert "v1.2.3" not in result
        assert result == "Cool Game"

    @patch("obs_clip_hook.get_active_window_class")
    @patch("obs_clip_hook.get_active_window_name")
    def test_detect_game_name_removes_parenthetical_content(self, mock_name, mock_class):
        """Should remove content in parentheses."""
        mock_name.return_value = "Game Title (Early Access)"
        mock_class.return_value = "unknown"

        result = detect_game_name()

        assert "(Early Access)" not in result


class TestFindLatestReplay:
    """Tests for find_latest_replay function."""

    def test_find_latest_replay_returns_empty_for_nonexistent_dir(self, tmp_path):
        """Should return empty string for non-existent directory."""
        result = find_latest_replay(str(tmp_path / "nonexistent"))

        assert result == ""

    def test_find_latest_replay_returns_empty_for_empty_dir(self, tmp_path):
        """Should return empty string when no video files exist."""
        result = find_latest_replay(str(tmp_path))

        assert result == ""

    def test_find_latest_replay_finds_mp4_files(self, tmp_path):
        """Should find .mp4 files."""
        video_file = tmp_path / "test.mp4"
        video_file.write_bytes(b"video")

        result = find_latest_replay(str(tmp_path))

        assert result == str(video_file)

    def test_find_latest_replay_finds_mkv_files(self, tmp_path):
        """Should find .mkv files."""
        video_file = tmp_path / "test.mkv"
        video_file.write_bytes(b"video")

        result = find_latest_replay(str(tmp_path))

        assert result == str(video_file)

    def test_find_latest_replay_returns_most_recent(self, tmp_path):
        """Should return the most recently modified file."""
        import time

        old_file = tmp_path / "old.mp4"
        old_file.write_bytes(b"old")

        time.sleep(0.1)  # Ensure different mtime

        new_file = tmp_path / "new.mp4"
        new_file.write_bytes(b"new")

        result = find_latest_replay(str(tmp_path))

        assert result == str(new_file)


class TestHandleReplaySaved:
    """Tests for handle_replay_saved function."""

    @patch("obs_clip_hook.play_audio_cue")
    @patch("obs_clip_hook.subprocess.Popen")
    @patch("obs_clip_hook.find_latest_replay")
    @patch("obs_clip_hook.get_replay_path")
    @patch("obs_clip_hook.detect_game_name")
    def test_handle_replay_saved_spawns_upload_subprocess(
        self, mock_detect, mock_replay_path, mock_find, mock_popen, mock_audio_cue, tmp_path
    ):
        """Should spawn upload subprocess with correct arguments."""
        from obs_clip_hook import handle_replay_saved

        # Set up the module state
        import obs_clip_hook

        obs_clip_hook.upload_script_path = "/path/to/upload_clip.py"
        obs_clip_hook.python_executable = "python3"

        # Create a test video file
        video_file = tmp_path / "Replay_2026-01-21_14-30-00.mp4"
        video_file.write_bytes(b"video")

        mock_detect.return_value = "Valorant"
        mock_replay_path.return_value = str(tmp_path)
        mock_find.return_value = str(video_file)

        # Mock os.path.exists to return True for upload script
        with patch("os.path.exists", return_value=True):
            handle_replay_saved()

        mock_popen.assert_called_once()
        call_args = mock_popen.call_args[0][0]
        assert call_args[0] == "python3"
        assert call_args[1] == "/path/to/upload_clip.py"
        assert "--file" in call_args
        assert "--title" in call_args
        assert "Valorant" in call_args[-1]  # Title includes game name

    @patch("obs_clip_hook.play_audio_cue")
    @patch("obs_clip_hook.subprocess.Popen")
    @patch("obs_clip_hook.find_latest_replay")
    @patch("obs_clip_hook.get_replay_path")
    @patch("obs_clip_hook.detect_game_name")
    def test_handle_replay_saved_renames_file(
        self, mock_detect, mock_replay_path, mock_find, mock_popen, mock_audio_cue, tmp_path
    ):
        """Should rename the replay file with game name and timestamp."""
        from obs_clip_hook import handle_replay_saved

        import obs_clip_hook

        obs_clip_hook.upload_script_path = "/path/to/upload_clip.py"
        obs_clip_hook.python_executable = "python3"

        # Create a test video file
        video_file = tmp_path / "Replay_2026-01-21_14-30-00.mp4"
        video_file.write_bytes(b"video")

        mock_detect.return_value = "TestGame"
        mock_replay_path.return_value = str(tmp_path)
        mock_find.return_value = str(video_file)

        with patch("os.path.exists", return_value=True):
            handle_replay_saved()

        # Original file should be renamed
        assert not video_file.exists()
        # New file should exist with game name
        renamed_files = list(tmp_path.glob("TestGame - *.mp4"))
        assert len(renamed_files) == 1

    @patch("obs_clip_hook.play_audio_cue")
    @patch("obs_clip_hook.find_latest_replay")
    @patch("obs_clip_hook.get_replay_path")
    def test_handle_replay_saved_logs_warning_when_no_upload_script(
        self, mock_replay_path, mock_find, mock_audio_cue
    ):
        """Should log warning when upload script path is not configured."""
        from obs_clip_hook import handle_replay_saved

        import obs_clip_hook

        obs_clip_hook.upload_script_path = ""

        handle_replay_saved()

        mock_obs.script_log.assert_called()
        # Should not proceed to find replay
        mock_find.assert_not_called()


class TestPlayAudioCue:
    """Tests for play_audio_cue function."""

    @patch("obs_clip_hook._run_host_command")
    def test_play_audio_cue_calls_paplay(self, mock_run, tmp_path):
        """Should call paplay with the audio file path."""
        # Create a temporary sounds directory with audio file
        sounds_dir = tmp_path / "sounds"
        sounds_dir.mkdir()
        audio_file = sounds_dir / "clip_saved.wav"
        audio_file.write_bytes(b"fake wav data")

        with patch("obs_clip_hook.Path") as mock_path:
            # Mock Path(__file__).parent to return tmp_path
            mock_path.return_value.parent = tmp_path

            play_audio_cue()

            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert call_args[0] == "paplay"
            assert "clip_saved.wav" in call_args[1]

    @patch("obs_clip_hook._run_host_command")
    def test_play_audio_cue_handles_missing_file(self, mock_run, tmp_path):
        """Should not call paplay when audio file doesn't exist."""
        with patch("obs_clip_hook.Path") as mock_path:
            mock_path.return_value.parent = tmp_path

            play_audio_cue()

            mock_run.assert_not_called()

    @patch("obs_clip_hook._run_host_command")
    def test_play_audio_cue_handles_exception(self, mock_run, tmp_path):
        """Should handle exceptions gracefully."""
        sounds_dir = tmp_path / "sounds"
        sounds_dir.mkdir()
        audio_file = sounds_dir / "clip_saved.wav"
        audio_file.write_bytes(b"fake wav data")

        mock_run.side_effect = Exception("paplay failed")

        with patch("obs_clip_hook.Path") as mock_path:
            mock_path.return_value.parent = tmp_path

            # Should not raise
            play_audio_cue()

            mock_obs.script_log.assert_called()
