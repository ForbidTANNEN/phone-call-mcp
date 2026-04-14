from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

CALENDAR_SCOPES: set[str] = {
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
}

DEFAULT_TOKEN_URI = "https://oauth2.googleapis.com/token"


@dataclass
class GoogleCredentials:
    client_id: str
    client_secret: str
    refresh_token: str
    token_uri: str = DEFAULT_TOKEN_URI
    source: str = ""


def _has_calendar_scope(scopes: object) -> bool:
    """Return True if any scope string contains 'calendar'."""
    if isinstance(scopes, (list, tuple)):
        return any("calendar" in str(s) for s in scopes)
    if isinstance(scopes, str):
        return "calendar" in scopes
    return False


def _load_json(path: Path) -> Optional[dict]:
    """Load JSON from path, returning None on any error."""
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _try_workspace_mcp(home: Path) -> Optional[GoogleCredentials]:
    creds_dir = home / ".google_workspace_mcp" / "credentials"
    if not creds_dir.is_dir():
        return None

    for json_file in sorted(creds_dir.glob("*.json")):
        data = _load_json(json_file)
        if data is None:
            continue

        scopes = data.get("scopes") or data.get("scope") or []
        if not _has_calendar_scope(scopes):
            continue

        client_id = data.get("client_id")
        client_secret = data.get("client_secret")
        refresh_token = data.get("refresh_token")
        if not (client_id and client_secret and refresh_token):
            continue

        return GoogleCredentials(
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
            token_uri=data.get("token_uri", DEFAULT_TOKEN_URI),
            source=f"workspace-mcp:{json_file}",
        )

    return None


def _try_adc(home: Path) -> Optional[GoogleCredentials]:
    adc_path = home / ".config" / "gcloud" / "application_default_credentials.json"
    if not adc_path.exists():
        return None

    data = _load_json(adc_path)
    if data is None:
        return None

    client_id = data.get("client_id")
    client_secret = data.get("client_secret")
    refresh_token = data.get("refresh_token")
    if not (client_id and client_secret and refresh_token):
        return None

    return GoogleCredentials(
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=refresh_token,
        token_uri=data.get("token_uri", DEFAULT_TOKEN_URI),
        source=f"adc:{adc_path}",
    )


def _try_dial_mcp(home: Path) -> Optional[GoogleCredentials]:
    creds_path = home / ".dial-mcp" / "credentials" / "google.json"
    if not creds_path.exists():
        return None

    data = _load_json(creds_path)
    if data is None:
        return None

    client_id = data.get("client_id")
    client_secret = data.get("client_secret")
    refresh_token = data.get("refresh_token")
    if not (client_id and client_secret and refresh_token):
        return None

    return GoogleCredentials(
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=refresh_token,
        token_uri=data.get("token_uri", DEFAULT_TOKEN_URI),
        source=f"dial-mcp:{creds_path}",
    )


def discover_google_credentials(home_dir: Optional[Path] = None) -> Optional[GoogleCredentials]:
    """Discover Google Calendar credentials from known locations.

    Priority order:
      1. ~/.google_workspace_mcp/credentials/*.json (must have calendar scope)
      2. ~/.config/gcloud/application_default_credentials.json
      3. ~/.dial-mcp/credentials/google.json
    """
    home = home_dir if home_dir is not None else Path.home()

    return (
        _try_workspace_mcp(home)
        or _try_adc(home)
        or _try_dial_mcp(home)
    )


def save_credentials(creds: GoogleCredentials, home_dir: Optional[Path] = None) -> Path:
    """Write credentials to ~/.dial-mcp/credentials/google.json with mode 0o600."""
    home = home_dir if home_dir is not None else Path.home()
    dest = home / ".dial-mcp" / "credentials" / "google.json"
    dest.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
    }
    dest.write_text(json.dumps(payload, indent=2))
    dest.chmod(0o600)
    return dest
