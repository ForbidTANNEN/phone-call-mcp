import json
import stat
import pytest
from pathlib import Path

from dial_mcp.calendar.credentials import (
    discover_google_credentials,
    save_credentials,
    GoogleCredentials,
    CALENDAR_SCOPES,
    DEFAULT_TOKEN_URI,
)

_CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar"


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


class TestDiscoverWorkspaceMcp:
    def test_finds_workspace_mcp_credentials(self, tmp_path):
        cred_file = tmp_path / ".google_workspace_mcp" / "credentials" / "user@example.com.json"
        _write_json(cred_file, {
            "client_id": "ws_client_id",
            "client_secret": "ws_client_secret",
            "refresh_token": "ws_refresh",
            "scopes": [_CALENDAR_SCOPE],
        })

        creds = discover_google_credentials(home_dir=tmp_path)

        assert creds is not None
        assert creds.client_id == "ws_client_id"
        assert creds.client_secret == "ws_client_secret"
        assert creds.refresh_token == "ws_refresh"
        assert creds.token_uri == DEFAULT_TOKEN_URI
        assert "workspace-mcp" in creds.source

    def test_skips_workspace_mcp_without_calendar_scope(self, tmp_path):
        cred_file = tmp_path / ".google_workspace_mcp" / "credentials" / "user@example.com.json"
        _write_json(cred_file, {
            "client_id": "ws_client_id",
            "client_secret": "ws_client_secret",
            "refresh_token": "ws_refresh",
            "scopes": ["https://www.googleapis.com/auth/drive"],
        })

        creds = discover_google_credentials(home_dir=tmp_path)

        assert creds is None

    def test_skips_malformed_json(self, tmp_path):
        cred_file = tmp_path / ".google_workspace_mcp" / "credentials" / "bad.json"
        cred_file.parent.mkdir(parents=True, exist_ok=True)
        cred_file.write_text("not { valid json !!!")

        creds = discover_google_credentials(home_dir=tmp_path)

        assert creds is None


class TestDiscoverDialMcp:
    def test_finds_dial_mcp_credentials(self, tmp_path):
        cred_file = tmp_path / ".dial-mcp" / "credentials" / "google.json"
        _write_json(cred_file, {
            "client_id": "dial_client_id",
            "client_secret": "dial_client_secret",
            "refresh_token": "dial_refresh",
        })

        creds = discover_google_credentials(home_dir=tmp_path)

        assert creds is not None
        assert creds.client_id == "dial_client_id"
        assert creds.refresh_token == "dial_refresh"
        assert "dial-mcp" in creds.source


class TestDiscoverPriority:
    def test_prefers_workspace_mcp_over_dial_mcp(self, tmp_path):
        # workspace-mcp cred with calendar scope
        ws_file = tmp_path / ".google_workspace_mcp" / "credentials" / "user@example.com.json"
        _write_json(ws_file, {
            "client_id": "ws_client_id",
            "client_secret": "ws_client_secret",
            "refresh_token": "ws_refresh",
            "scopes": [_CALENDAR_SCOPE],
        })

        # dial-mcp cred
        dial_file = tmp_path / ".dial-mcp" / "credentials" / "google.json"
        _write_json(dial_file, {
            "client_id": "dial_client_id",
            "client_secret": "dial_client_secret",
            "refresh_token": "dial_refresh",
        })

        creds = discover_google_credentials(home_dir=tmp_path)

        assert creds is not None
        assert creds.client_id == "ws_client_id"
        assert "workspace-mcp" in creds.source


class TestDiscoverNone:
    def test_returns_none_when_no_credentials(self, tmp_path):
        creds = discover_google_credentials(home_dir=tmp_path)
        assert creds is None


class TestSaveCredentials:
    def test_saves_to_dial_mcp_path(self, tmp_path):
        creds = GoogleCredentials(
            client_id="save_client",
            client_secret="save_secret",
            refresh_token="save_refresh",
        )
        dest = save_credentials(creds, home_dir=tmp_path)

        assert dest == tmp_path / ".dial-mcp" / "credentials" / "google.json"
        assert dest.exists()

        data = json.loads(dest.read_text())
        assert data["client_id"] == "save_client"
        assert data["client_secret"] == "save_secret"
        assert data["refresh_token"] == "save_refresh"
        assert data["token_uri"] == DEFAULT_TOKEN_URI

    def test_saves_with_mode_600(self, tmp_path):
        creds = GoogleCredentials(
            client_id="c",
            client_secret="s",
            refresh_token="r",
        )
        dest = save_credentials(creds, home_dir=tmp_path)
        file_mode = stat.S_IMODE(dest.stat().st_mode)
        assert file_mode == 0o600
