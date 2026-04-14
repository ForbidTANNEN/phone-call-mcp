from __future__ import annotations

import logging
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

from dial_mcp.calendar.credentials import GoogleCredentials, save_credentials

logger = logging.getLogger("dial-mcp.calendar")

# dial-mcp's own OAuth client — registered as a "Desktop" app in GCP.
# Users can override via config.yaml if they hit rate limits.
# TODO: Replace with real client ID before publishing.
BUNDLED_CLIENT_CONFIG = {
    "installed": {
        "client_id": "REPLACE_BEFORE_PUBLISH.apps.googleusercontent.com",
        "client_secret": "REPLACE_BEFORE_PUBLISH",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }
}

CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events.readonly",
]


def run_oauth_flow(
    client_config: dict | None = None,
    home_dir: Path | None = None,
) -> GoogleCredentials:
    """Run OAuth browser flow. Opens browser, user clicks Allow, saves token."""
    config = client_config or BUNDLED_CLIENT_CONFIG

    flow = InstalledAppFlow.from_client_config(config, scopes=CALENDAR_SCOPES)

    google_creds = flow.run_local_server(
        port=0,
        open_browser=True,
        prompt="consent",
        success_message="Calendar linked! You can close this tab.",
    )

    client_info = config.get("installed", config.get("web", {}))

    creds = GoogleCredentials(
        client_id=client_info["client_id"],
        client_secret=client_info["client_secret"],
        refresh_token=google_creds.refresh_token,
        token_uri=client_info.get("token_uri", "https://oauth2.googleapis.com/token"),
        source="dial-mcp",
    )

    save_credentials(creds, home_dir=home_dir)
    logger.info("Google Calendar credentials saved")
    return creds
