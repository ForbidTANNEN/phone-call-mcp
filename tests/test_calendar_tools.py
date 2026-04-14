import pytest
from unittest.mock import patch, MagicMock
from dial_mcp.calendar.tools import build_calendar_tools
from dial_mcp.calendar.credentials import GoogleCredentials


@pytest.fixture
def mock_creds():
    return GoogleCredentials(
        client_id="test.apps.googleusercontent.com",
        client_secret="test_secret",
        refresh_token="1//test",
        source="test",
    )


class TestBuildCalendarTools:
    def test_returns_three_tools(self, mock_creds):
        with patch("dial_mcp.calendar.tools.CalendarClient"):
            tools = build_calendar_tools(mock_creds)
        assert len(tools) == 3

    def test_tool_names(self, mock_creds):
        with patch("dial_mcp.calendar.tools.CalendarClient"):
            tools = build_calendar_tools(mock_creds)
        names = {t.info.name for t in tools}
        assert "check_calendar" in names
        assert "check_availability" in names
        assert "get_todays_schedule" in names
