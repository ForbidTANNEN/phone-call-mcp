from __future__ import annotations

import logging
from datetime import datetime

from livekit.agents import function_tool

from dial_mcp.calendar.client import CalendarClient
from dial_mcp.calendar.credentials import GoogleCredentials

logger = logging.getLogger("dial-mcp.calendar")


def build_calendar_tools(creds: GoogleCredentials) -> list:
    """Build LiveKit function_tools using the given credentials.

    Returns list of decorated functions for AgentSession(tools=[...]).
    """
    client = CalendarClient(creds)

    @function_tool(name="check_calendar")
    async def check_calendar(date: str) -> str:
        """Check what events are on the calendar for a specific date.

        Args:
            date: The date to check in YYYY-MM-DD format (e.g. 2026-04-14)
        """
        try:
            return client.list_events_voice(date, date)
        except Exception as e:
            logger.error(f"Calendar lookup failed: {e}")
            return "I wasn't able to check the calendar right now."

    @function_tool(name="check_availability")
    async def check_availability(date: str) -> str:
        """Check available time slots on a specific date.

        Args:
            date: The date to check in YYYY-MM-DD format (e.g. 2026-04-14)
        """
        try:
            return client.availability_voice(date)
        except Exception as e:
            logger.error(f"Availability check failed: {e}")
            return "I wasn't able to check availability right now."

    @function_tool(name="get_todays_schedule")
    async def get_todays_schedule() -> str:
        """Get today's calendar schedule."""
        today = datetime.now().strftime("%Y-%m-%d")
        try:
            return client.list_events_voice(today, today)
        except Exception as e:
            logger.error(f"Schedule lookup failed: {e}")
            return "I wasn't able to check today's schedule."

    return [check_calendar, check_availability, get_todays_schedule]
