"""Tests for auth_setup.py."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestAuthSetup:
    """Tests for auth_setup.py main function."""

    def test_auth_setup_exits_when_credentials_missing(self, tmp_path, capsys):
        """Should exit with error when credentials.json is missing."""
        # Create config dir but not credentials file
        config_dir = tmp_path / ".config" / "obs-yt-clipper"
        config_dir.mkdir(parents=True)

        # Patch module-level constants before importing
        with patch.dict("sys.modules", {"auth_setup": None}):
            # Remove cached module if present
            if "auth_setup" in sys.modules:
                del sys.modules["auth_setup"]

            with patch("pathlib.Path.home", return_value=tmp_path):
                import auth_setup
                # Reload to pick up patched Path.home
                import importlib
                importlib.reload(auth_setup)

                with pytest.raises(SystemExit) as exc_info:
                    auth_setup.main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Credentials file not found" in captured.out

    def test_auth_setup_saves_token_on_success(self, tmp_path, capsys):
        """Should save token file after successful authentication."""
        # Create config dir and credentials file
        config_dir = tmp_path / ".config" / "obs-yt-clipper"
        config_dir.mkdir(parents=True)
        credentials_file = config_dir / "credentials.json"
        credentials_file.write_text('{"installed": {"client_id": "test"}}')

        # Mock the OAuth flow
        mock_creds = MagicMock()
        mock_creds.to_json.return_value = '{"token": "test_token", "refresh_token": "refresh"}'
        mock_flow_instance = MagicMock()
        mock_flow_instance.run_local_server.return_value = mock_creds

        # Remove cached module and reimport with patched home
        if "auth_setup" in sys.modules:
            del sys.modules["auth_setup"]

        with patch("pathlib.Path.home", return_value=tmp_path):
            import auth_setup
            import importlib
            importlib.reload(auth_setup)

            with patch.object(auth_setup, "InstalledAppFlow") as mock_flow:
                mock_flow.from_client_secrets_file.return_value = mock_flow_instance
                auth_setup.main()

            # Check token was saved
            token_file = config_dir / "token.json"
            assert token_file.exists()
            assert "test_token" in token_file.read_text()

        captured = capsys.readouterr()
        assert "Success" in captured.out

    @patch("auth_setup.InstalledAppFlow")
    def test_auth_setup_handles_auth_error(self, mock_flow, tmp_path, capsys):
        """Should handle authentication errors gracefully."""
        # Create config dir and credentials file
        config_dir = tmp_path / ".config" / "obs-yt-clipper"
        config_dir.mkdir(parents=True)
        credentials_file = config_dir / "credentials.json"
        credentials_file.write_text('{"installed": {"client_id": "test"}}')

        # Mock the OAuth flow to raise an error
        mock_flow.from_client_secrets_file.side_effect = Exception("Auth failed")

        # Remove cached module and reimport with patched home
        if "auth_setup" in sys.modules:
            del sys.modules["auth_setup"]

        with patch("pathlib.Path.home", return_value=tmp_path):
            import auth_setup
            import importlib
            importlib.reload(auth_setup)

            with pytest.raises(SystemExit) as exc_info:
                auth_setup.main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Error" in captured.out

    def test_auth_setup_requests_upload_scope(self, tmp_path):
        """Should request YouTube upload scope."""
        # Create config dir and credentials file
        config_dir = tmp_path / ".config" / "obs-yt-clipper"
        config_dir.mkdir(parents=True)
        credentials_file = config_dir / "credentials.json"
        credentials_file.write_text('{"installed": {"client_id": "test"}}')

        # Mock the OAuth flow
        mock_creds = MagicMock()
        mock_creds.to_json.return_value = '{"token": "test"}'
        mock_flow_instance = MagicMock()
        mock_flow_instance.run_local_server.return_value = mock_creds

        # Remove cached module and reimport with patched home
        if "auth_setup" in sys.modules:
            del sys.modules["auth_setup"]

        with patch("pathlib.Path.home", return_value=tmp_path):
            import auth_setup
            import importlib
            importlib.reload(auth_setup)

            with patch.object(auth_setup, "InstalledAppFlow") as mock_flow:
                mock_flow.from_client_secrets_file.return_value = mock_flow_instance
                auth_setup.main()

                # Check correct scope was requested
                call_args = mock_flow.from_client_secrets_file.call_args
                scopes = call_args[0][1]
                assert "https://www.googleapis.com/auth/youtube.upload" in scopes
