from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date, timedelta, timezone
from typing import Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from dial_mcp.calendar.credentials import GoogleCredentials


@dataclass
class CalendarEvent:
    id: str
    summary: str
    start: datetime
    end: datetime
    all_day: bool


@dataclass
class TimeSlot:
    start: datetime
    end: datetime

    @property
    def duration_minutes(self) -> int:
        delta = self.end - self.start
        return int(delta.total_seconds() // 60)

    def voice_str(self) -> str:
        start_s = self.start.strftime("%-I:%M %p").lower()
        end_s = self.end.strftime("%-I:%M %p").lower()
        return f"{start_s} to {end_s}"


def _parse_google_dt(entry: dict) -> tuple[datetime, bool]:
    """Parse a Google Calendar start/end dict, returning (datetime, all_day)."""
    if "dateTime" in entry:
        dt = datetime.fromisoformat(entry["dateTime"])
        # Ensure timezone-aware; if naive, treat as UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt, False
    else:
        # All-day event — "date" key, e.g. "2025-06-01"
        d = date.fromisoformat(entry["date"])
        dt = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
        return dt, True


class CalendarClient:
    def __init__(self, creds: GoogleCredentials) -> None:
        self._creds = creds
        self._service = self._build_service()

    def _build_service(self):
        google_creds = Credentials(
            token=None,
            refresh_token=self._creds.refresh_token,
            token_uri=self._creds.token_uri,
            client_id=self._creds.client_id,
            client_secret=self._creds.client_secret,
        )
        return build("calendar", "v3", credentials=google_creds, cache_discovery=False)

    def list_events(self, date_start: str, date_end: str) -> list[CalendarEvent]:
        """Return CalendarEvent objects between date_start and date_end (YYYY-MM-DD)."""
        time_min = f"{date_start}T00:00:00Z"
        time_max = f"{date_end}T23:59:59Z"

        result = (
            self._service.events()
            .list(
                calendarId="primary",
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events: list[CalendarEvent] = []
        for item in result.get("items", []):
            start, all_day = _parse_google_dt(item.get("start", {}))
            end, _ = _parse_google_dt(item.get("end", {}))
            events.append(
                CalendarEvent(
                    id=item.get("id", ""),
                    summary=item.get("summary", "(no title)"),
                    start=start,
                    end=end,
                    all_day=all_day,
                )
            )
        return events

    def check_availability(
        self, date: str, start_hour: int = 9, end_hour: int = 17
    ) -> list[TimeSlot]:
        """Return free TimeSlots on the given date between start_hour and end_hour."""
        time_min = f"{date}T00:00:00Z"
        time_max = f"{date}T23:59:59Z"

        body = {
            "timeMin": time_min,
            "timeMax": time_max,
            "items": [{"id": "primary"}],
        }
        result = self._service.freebusy().query(body=body).execute()
        busy_periods = result.get("calendars", {}).get("primary", {}).get("busy", [])

        # Build window in UTC
        day = datetime.fromisoformat(date).replace(tzinfo=timezone.utc)
        window_start = day.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        window_end = day.replace(hour=end_hour, minute=0, second=0, microsecond=0)

        # Parse busy intervals, clamped to window
        busy: list[tuple[datetime, datetime]] = []
        for period in busy_periods:
            b_start = datetime.fromisoformat(period["start"].replace("Z", "+00:00"))
            b_end = datetime.fromisoformat(period["end"].replace("Z", "+00:00"))
            # Clamp to window
            b_start = max(b_start, window_start)
            b_end = min(b_end, window_end)
            if b_start < b_end:
                busy.append((b_start, b_end))

        # Sort busy periods and compute gaps
        busy.sort(key=lambda x: x[0])
        free: list[TimeSlot] = []
        cursor = window_start

        for b_start, b_end in busy:
            if cursor < b_start:
                free.append(TimeSlot(start=cursor, end=b_start))
            cursor = max(cursor, b_end)

        if cursor < window_end:
            free.append(TimeSlot(start=cursor, end=window_end))

        return free

    def list_events_voice(self, date_start: str, date_end: str) -> str:
        """Voice-friendly summary of events, e.g. '3:00 pm: Dr appointment'."""
        events = self.list_events(date_start, date_end)
        if not events:
            return "No events found."
        lines = []
        for ev in events:
            if ev.all_day:
                lines.append(f"All day: {ev.summary}")
            else:
                time_s = ev.start.strftime("%-I:%M %p").lower()
                lines.append(f"{time_s}: {ev.summary}")
        return "\n".join(lines)

    def availability_voice(self, date: str) -> str:
        """Voice-friendly summary of free slots on a given date."""
        slots = self.check_availability(date)
        if not slots:
            return "No free time available."
        parts = [slot.voice_str() for slot in slots]
        return "Free: " + ", ".join(parts)
