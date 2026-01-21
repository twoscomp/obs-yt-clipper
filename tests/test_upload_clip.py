"""Tests for upload_clip.py."""

import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from upload_clip import (
    load_config,
    setup_logging,
    send_notification,
    get_youtube_service,
    upload_video,
    upload_with_retry,
)


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_config_returns_defaults_when_file_missing(self, tmp_path):
        """Should return default config when file doesn't exist."""
        config = load_config(tmp_path / "nonexistent.yaml")

        assert config["youtube"]["privacy"] == "unlisted"
        assert config["retry"]["max_attempts"] == 3
        assert config["retry"]["backoff_seconds"] == 30

    def test_load_config_reads_yaml_file(self, tmp_path):
        """Should load configuration from YAML file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
youtube:
  privacy: public
  description_template: "Test {date}"
retry:
  max_attempts: 5
  backoff_seconds: 10
credentials_path: /path/to/creds.json
token_path: /path/to/token.json
log_path: /path/to/log.log
""")

        config = load_config(config_file)

        assert config["youtube"]["privacy"] == "public"
        assert config["retry"]["max_attempts"] == 5
        assert config["retry"]["backoff_seconds"] == 10


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_setup_logging_creates_log_directory(self, tmp_path):
        """Should create log directory if it doesn't exist."""
        log_path = tmp_path / "logs" / "subdir" / "uploads.log"

        logger = setup_logging(str(log_path))

        assert log_path.parent.exists()
        assert logger.name == "upload_clip"

    def test_setup_logging_returns_configured_logger(self, tmp_path):
        """Should return a properly configured logger."""
        log_path = tmp_path / "uploads.log"

        logger = setup_logging(str(log_path))

        assert logger.level == logging.DEBUG
        assert len(logger.handlers) >= 2  # File and stderr handlers


class TestSendNotification:
    """Tests for send_notification function."""

    @patch("upload_clip.subprocess.run")
    def test_send_notification_calls_notify_send(self, mock_run):
        """Should call notify-send with correct arguments."""
        send_notification("Test Title", "Test message")

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "notify-send"
        assert "-u" in args
        assert "normal" in args
        assert "Test Title" in args
        assert "Test message" in args

    @patch("upload_clip.subprocess.run")
    def test_send_notification_with_urgency(self, mock_run):
        """Should pass urgency level to notify-send."""
        send_notification("Title", "Message", urgency="critical")

        args = mock_run.call_args[0][0]
        assert "critical" in args

    @patch("upload_clip.subprocess.run", side_effect=FileNotFoundError)
    def test_send_notification_handles_missing_notify_send(self, mock_run):
        """Should not raise when notify-send is not installed."""
        # Should not raise
        send_notification("Title", "Message")


class TestGetYoutubeService:
    """Tests for get_youtube_service function."""

    def test_get_youtube_service_raises_on_missing_token(self, tmp_path):
        """Should raise FileNotFoundError when token file doesn't exist."""
        logger = MagicMock()

        with pytest.raises(FileNotFoundError):
            get_youtube_service(str(tmp_path / "missing_token.json"), logger)

    @patch("upload_clip.build")
    @patch("upload_clip.Credentials.from_authorized_user_file")
    def test_get_youtube_service_builds_service(self, mock_creds, mock_build, tmp_path):
        """Should build YouTube service with valid credentials."""
        token_file = tmp_path / "token.json"
        token_file.write_text('{"token": "test"}')

        mock_creds_instance = MagicMock()
        mock_creds_instance.expired = False
        mock_creds.return_value = mock_creds_instance

        logger = MagicMock()

        get_youtube_service(str(token_file), logger)

        mock_build.assert_called_once_with("youtube", "v3", credentials=mock_creds_instance)

    @patch("google.auth.transport.requests.Request")
    @patch("upload_clip.build")
    @patch("upload_clip.Credentials.from_authorized_user_file")
    def test_get_youtube_service_refreshes_expired_credentials(
        self, mock_creds, mock_build, mock_request, tmp_path
    ):
        """Should refresh credentials when expired."""
        token_file = tmp_path / "token.json"
        token_file.write_text('{"token": "test"}')

        mock_creds_instance = MagicMock()
        mock_creds_instance.expired = True
        mock_creds_instance.refresh_token = "refresh_token"
        mock_creds_instance.to_json.return_value = '{"refreshed": "token"}'
        mock_creds.return_value = mock_creds_instance

        logger = MagicMock()

        get_youtube_service(str(token_file), logger)

        mock_creds_instance.refresh.assert_called_once()


class TestUploadVideo:
    """Tests for upload_video function."""

    @patch("upload_clip.MediaFileUpload")
    def test_upload_video_returns_video_id(self, mock_media, mock_youtube_service, temp_video_file):
        """Should return video ID on successful upload."""
        logger = MagicMock()

        video_id = upload_video(
            youtube=mock_youtube_service,
            file_path=str(temp_video_file),
            title="Test Title",
            description="Test Description",
            privacy="unlisted",
            logger=logger,
        )

        assert video_id == "test_video_id_123"

    @patch("upload_clip.MediaFileUpload")
    def test_upload_video_sets_correct_metadata(self, mock_media, mock_youtube_service, temp_video_file):
        """Should set correct video metadata."""
        logger = MagicMock()

        upload_video(
            youtube=mock_youtube_service,
            file_path=str(temp_video_file),
            title="My Game Clip",
            description="Cool moment",
            privacy="private",
            logger=logger,
        )

        # Check the insert call
        insert_call = mock_youtube_service.videos().insert
        insert_call.assert_called_once()
        call_kwargs = insert_call.call_args[1]

        assert call_kwargs["body"]["snippet"]["title"] == "My Game Clip"
        assert call_kwargs["body"]["snippet"]["description"] == "Cool moment"
        assert call_kwargs["body"]["status"]["privacyStatus"] == "private"
        assert call_kwargs["body"]["snippet"]["categoryId"] == "20"  # Gaming


class TestUploadWithRetry:
    """Tests for upload_with_retry function."""

    @patch("upload_clip.upload_video")
    def test_upload_with_retry_succeeds_on_first_attempt(self, mock_upload, mock_youtube_service):
        """Should return video ID when upload succeeds immediately."""
        mock_upload.return_value = "video_123"
        logger = MagicMock()

        result = upload_with_retry(
            youtube=mock_youtube_service,
            file_path="/path/to/video.mp4",
            title="Test",
            description="Desc",
            privacy="unlisted",
            max_attempts=3,
            backoff_seconds=1,
            logger=logger,
        )

        assert result == "video_123"
        assert mock_upload.call_count == 1

    @patch("upload_clip.time.sleep")
    @patch("upload_clip.upload_video")
    def test_upload_with_retry_retries_on_failure(self, mock_upload, mock_sleep, mock_youtube_service):
        """Should retry on transient failures."""
        mock_upload.side_effect = [Exception("Network error"), "video_456"]
        logger = MagicMock()

        result = upload_with_retry(
            youtube=mock_youtube_service,
            file_path="/path/to/video.mp4",
            title="Test",
            description="Desc",
            privacy="unlisted",
            max_attempts=3,
            backoff_seconds=1,
            logger=logger,
        )

        assert result == "video_456"
        assert mock_upload.call_count == 2
        mock_sleep.assert_called_once_with(1)  # First backoff

    @patch("upload_clip.time.sleep")
    @patch("upload_clip.upload_video")
    def test_upload_with_retry_uses_exponential_backoff(self, mock_upload, mock_sleep, mock_youtube_service):
        """Should use exponential backoff between retries."""
        mock_upload.side_effect = [
            Exception("Error 1"),
            Exception("Error 2"),
            "video_789",
        ]
        logger = MagicMock()

        upload_with_retry(
            youtube=mock_youtube_service,
            file_path="/path/to/video.mp4",
            title="Test",
            description="Desc",
            privacy="unlisted",
            max_attempts=3,
            backoff_seconds=2,
            logger=logger,
        )

        # Should backoff: 2 seconds, then 4 seconds
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(2)
        mock_sleep.assert_any_call(4)

    @patch("upload_clip.time.sleep")
    @patch("upload_clip.upload_video")
    def test_upload_with_retry_raises_after_max_attempts(self, mock_upload, mock_sleep, mock_youtube_service):
        """Should raise last error after exhausting all attempts."""
        mock_upload.side_effect = Exception("Persistent error")
        logger = MagicMock()

        with pytest.raises(Exception, match="Persistent error"):
            upload_with_retry(
                youtube=mock_youtube_service,
                file_path="/path/to/video.mp4",
                title="Test",
                description="Desc",
                privacy="unlisted",
                max_attempts=3,
                backoff_seconds=1,
                logger=logger,
            )

        assert mock_upload.call_count == 3

    @patch("upload_clip.upload_video")
    def test_upload_with_retry_raises_immediately_on_client_error(self, mock_upload, mock_youtube_service):
        """Should raise immediately on non-retryable HTTP errors."""
        from googleapiclient.errors import HttpError

        mock_response = MagicMock()
        mock_response.status = 403  # Forbidden - not retryable
        mock_upload.side_effect = HttpError(mock_response, b"Forbidden")
        logger = MagicMock()

        with pytest.raises(HttpError):
            upload_with_retry(
                youtube=mock_youtube_service,
                file_path="/path/to/video.mp4",
                title="Test",
                description="Desc",
                privacy="unlisted",
                max_attempts=3,
                backoff_seconds=1,
                logger=logger,
            )

        assert mock_upload.call_count == 1  # No retries
