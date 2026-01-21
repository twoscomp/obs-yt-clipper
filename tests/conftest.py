"""Shared fixtures for tests."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock


@pytest.fixture
def temp_config_dir(tmp_path):
    """Create a temporary config directory structure."""
    config_dir = tmp_path / ".config" / "obs-yt-clipper"
    config_dir.mkdir(parents=True)
    return config_dir


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create a temporary data directory structure."""
    data_dir = tmp_path / ".local" / "share" / "obs-yt-clipper"
    data_dir.mkdir(parents=True)
    return data_dir


@pytest.fixture
def sample_config(temp_config_dir, temp_data_dir):
    """Create a sample configuration dictionary."""
    return {
        "youtube": {
            "privacy": "unlisted",
            "description_template": "Recorded on {date}",
        },
        "credentials_path": str(temp_config_dir / "credentials.json"),
        "token_path": str(temp_config_dir / "token.json"),
        "log_path": str(temp_data_dir / "uploads.log"),
        "retry": {
            "max_attempts": 3,
            "backoff_seconds": 1,  # Short for testing
        },
    }


@pytest.fixture
def mock_youtube_service():
    """Create a mock YouTube API service."""
    mock_service = MagicMock()
    mock_videos = MagicMock()
    mock_insert = MagicMock()

    # Set up the chain: youtube.videos().insert()
    mock_service.videos.return_value = mock_videos
    mock_videos.insert.return_value = mock_insert

    # Mock the upload response
    mock_insert.next_chunk.return_value = (None, {"id": "test_video_id_123"})

    return mock_service


@pytest.fixture
def temp_video_file(tmp_path):
    """Create a temporary video file for testing."""
    video_file = tmp_path / "test_video.mp4"
    video_file.write_bytes(b"fake video content")
    return video_file
