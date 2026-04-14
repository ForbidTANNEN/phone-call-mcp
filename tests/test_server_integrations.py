import json
import pytest
from unittest.mock import patch, MagicMock
from dial_mcp.server import handle_list_integrations, handle_link_calendar


class TestListIntegrations:
    @pytest.mark.asyncio
    async def test_returns_linked_when_creds_exist(self):
        mock_creds = MagicMock()
        mock_creds.source = "workspace-mcp"
        with patch("dial_mcp.server.discover_google_credentials", return_value=mock_creds):
            result = await handle_list_integrations()
        data = json.loads(result[0].text)
        assert data["google_calendar"]["status"] == "linked"
        assert data["google_calendar"]["source"] == "workspace-mcp"

    @pytest.mark.asyncio
    async def test_returns_not_linked_when_no_creds(self):
        with patch("dial_mcp.server.discover_google_credentials", return_value=None):
            result = await handle_list_integrations()
        data = json.loads(result[0].text)
        assert data["google_calendar"]["status"] == "not_linked"


class TestLinkCalendar:
    @pytest.mark.asyncio
    async def test_returns_already_linked_if_creds_exist(self):
        mock_creds = MagicMock()
        mock_creds.source = "workspace-mcp"
        with patch("dial_mcp.server.discover_google_credentials", return_value=mock_creds):
            result = await handle_link_calendar({"provider": "google"})
        data = json.loads(result[0].text)
        assert data["status"] == "already_linked"

    @pytest.mark.asyncio
    async def test_rejects_unsupported_provider(self):
        result = await handle_link_calendar({"provider": "outlook"})
        data = json.loads(result[0].text)
        assert "error" in data
