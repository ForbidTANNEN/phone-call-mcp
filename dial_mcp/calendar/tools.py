import logging
from datetime import datetime

from livekit.agents import function_tool

from dial_mcp.calendar.client import CalendarClient
from dial_mcp.calendar.credentials import GoogleCredentials

logger = logging.getLogger("dial-mcp.calendar")


def build_calendar_tools(creds: GoogleCredentials) -> list:
    """Build LiveKit function_tools using the given credentials.

    Returns list of decorated functions for AgentSession(tools=[...]).
    The CalendarClient is lazy-initialized on first tool call to avoid
    blocking the event loop with googleapiclient.discovery.build() at startup.
    """
    _client = None

    def _get_client() -> CalendarClient:
        nonlocal _client
        if _client is None:
            _client = CalendarClient(creds)
        return _client

    @function_tool(name="check_calendar")
    async def check_calendar(date: str) -> str:
        """Check what events are on the calendar for a specific date.

        Args:
            date: The date to check in YYYY-MM-DD format (e.g. 2026-04-14)
        """
        try:
            import asyncio
            client = await asyncio.get_event_loop().run_in_executor(None, _get_client)
            return await asyncio.get_event_loop().run_in_executor(
                None, client.list_events_voice, date, date
            )
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
            import asyncio
            client = await asyncio.get_event_loop().run_in_executor(None, _get_client)
            return await asyncio.get_event_loop().run_in_executor(
                None, client.availability_voice, date
            )
        except Exception as e:
            logger.error(f"Availability check failed: {e}")
            return "I wasn't able to check availability right now."

    @function_tool(name="get_todays_schedule")
    async def get_todays_schedule() -> str:
        """Get today's calendar schedule."""
        today = datetime.now().strftime("%Y-%m-%d")
        try:
            import asyncio
            client = await asyncio.get_event_loop().run_in_executor(None, _get_client)
            return await asyncio.get_event_loop().run_in_executor(
                None, client.list_events_voice, today, today
            )
        except Exception as e:
            logger.error(f"Schedule lookup failed: {e}")
            return "I wasn't able to check today's schedule."

    return [check_calendar, check_availability, get_todays_schedule]
