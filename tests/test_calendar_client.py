from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from dial_mcp.calendar.client import CalendarClient, CalendarEvent, TimeSlot
from dial_mcp.calendar.credentials import GoogleCredentials


FAKE_CREDS = GoogleCredentials(
    client_id="fake-client-id",
    client_secret="fake-client-secret",
    refresh_token="fake-refresh-token",
)


def _make_client(mock_service: MagicMock) -> CalendarClient:
    with patch.object(CalendarClient, "_build_service", return_value=mock_service):
        return CalendarClient(FAKE_CREDS)


class TestListEvents:
    def test_list_events_returns_calendar_events(self):
        mock_service = MagicMock()
        mock_service.events.return_value.list.return_value.execute.return_value = {
            "items": [
                {
                    "id": "event-1",
                    "summary": "Team standup",
                    "start": {"dateTime": "2025-06-10T09:00:00+00:00"},
                    "end": {"dateTime": "2025-06-10T09:30:00+00:00"},
                },
                {
                    "id": "event-2",
                    "summary": "Lunch",
                    "start": {"dateTime": "2025-06-10T12:00:00+00:00"},
                    "end": {"dateTime": "2025-06-10T13:00:00+00:00"},
                },
            ]
        }

        client = _make_client(mock_service)
        events = client.list_events("2025-06-10", "2025-06-10")

        assert len(events) == 2

        assert isinstance(events[0], CalendarEvent)
        assert events[0].id == "event-1"
        assert events[0].summary == "Team standup"
        assert events[0].start == datetime(2025, 6, 10, 9, 0, tzinfo=timezone.utc)
        assert events[0].end == datetime(2025, 6, 10, 9, 30, tzinfo=timezone.utc)
        assert events[0].all_day is False

        assert isinstance(events[1], CalendarEvent)
        assert events[1].id == "event-2"
        assert events[1].summary == "Lunch"
        assert events[1].start == datetime(2025, 6, 10, 12, 0, tzinfo=timezone.utc)
        assert events[1].all_day is False

    def test_list_events_handles_all_day_events(self):
        mock_service = MagicMock()
        mock_service.events.return_value.list.return_value.execute.return_value = {
            "items": [
                {
                    "id": "event-allday",
                    "summary": "Company holiday",
                    "start": {"date": "2025-06-11"},
                    "end": {"date": "2025-06-12"},
                }
            ]
        }

        client = _make_client(mock_service)
        events = client.list_events("2025-06-11", "2025-06-11")

        assert len(events) == 1
        assert events[0].all_day is True
        assert events[0].summary == "Company holiday"

    def test_list_events_empty(self):
        mock_service = MagicMock()
        mock_service.events.return_value.list.return_value.execute.return_value = {"items": []}

        client = _make_client(mock_service)
        events = client.list_events("2025-06-10", "2025-06-10")

        assert events == []


class TestCheckAvailability:
    def test_check_availability_returns_free_slots(self):
        mock_service = MagicMock()
        mock_service.freebusy.return_value.query.return_value.execute.return_value = {
            "calendars": {
                "primary": {
                    "busy": [
                        {
                            "start": "2025-06-10T10:00:00Z",
                            "end": "2025-06-10T11:00:00Z",
                        },
                        {
                            "start": "2025-06-10T13:00:00Z",
                            "end": "2025-06-10T14:00:00Z",
                        },
                    ]
                }
            }
        }

        client = _make_client(mock_service)
        slots = client.check_availability("2025-06-10", start_hour=9, end_hour=17)

        # Expected free slots: 9-10, 11-13, 14-17
        assert len(slots) == 3

        assert isinstance(slots[0], TimeSlot)
        assert slots[0].start == datetime(2025, 6, 10, 9, 0, tzinfo=timezone.utc)
        assert slots[0].end == datetime(2025, 6, 10, 10, 0, tzinfo=timezone.utc)

        assert slots[1].start == datetime(2025, 6, 10, 11, 0, tzinfo=timezone.utc)
        assert slots[1].end == datetime(2025, 6, 10, 13, 0, tzinfo=timezone.utc)

        assert slots[2].start == datetime(2025, 6, 10, 14, 0, tzinfo=timezone.utc)
        assert slots[2].end == datetime(2025, 6, 10, 17, 0, tzinfo=timezone.utc)

    def test_check_availability_no_busy_periods(self):
        mock_service = MagicMock()
        mock_service.freebusy.return_value.query.return_value.execute.return_value = {
            "calendars": {"primary": {"busy": []}}
        }

        client = _make_client(mock_service)
        slots = client.check_availability("2025-06-10", start_hour=9, end_hour=17)

        assert len(slots) == 1
        assert slots[0].start == datetime(2025, 6, 10, 9, 0, tzinfo=timezone.utc)
        assert slots[0].end == datetime(2025, 6, 10, 17, 0, tzinfo=timezone.utc)

    def test_check_availability_fully_booked(self):
        mock_service = MagicMock()
        mock_service.freebusy.return_value.query.return_value.execute.return_value = {
            "calendars": {
                "primary": {
                    "busy": [{"start": "2025-06-10T09:00:00Z", "end": "2025-06-10T17:00:00Z"}]
                }
            }
        }

        client = _make_client(mock_service)
        slots = client.check_availability("2025-06-10", start_hour=9, end_hour=17)

        assert slots == []


class TestTimeslot:
    def test_duration_minutes(self):
        slot = TimeSlot(
            start=datetime(2025, 6, 10, 9, 0, tzinfo=timezone.utc),
            end=datetime(2025, 6, 10, 10, 30, tzinfo=timezone.utc),
        )
        assert slot.duration_minutes == 90

    def test_voice_str(self):
        slot = TimeSlot(
            start=datetime(2025, 6, 10, 9, 0, tzinfo=timezone.utc),
            end=datetime(2025, 6, 10, 10, 30, tzinfo=timezone.utc),
        )
        assert slot.voice_str() == "9:00 am to 10:30 am"


class TestVoiceFormatting:
    def test_format_events_voice_friendly(self):
        mock_service = MagicMock()
        mock_service.events.return_value.list.return_value.execute.return_value = {
            "items": [
                {
                    "id": "e1",
                    "summary": "Dr appointment",
                    "start": {"dateTime": "2025-06-10T15:00:00+00:00"},
                    "end": {"dateTime": "2025-06-10T16:00:00+00:00"},
                },
                {
                    "id": "e2",
                    "summary": "Team standup",
                    "start": {"dateTime": "2025-06-10T09:30:00+00:00"},
                    "end": {"dateTime": "2025-06-10T10:00:00+00:00"},
                },
            ]
        }

        client = _make_client(mock_service)
        result = client.list_events_voice("2025-06-10", "2025-06-10")

        assert "3:00 pm" in result
        assert "Dr appointment" in result
        assert "9:30 am" in result
        assert "Team standup" in result

    def test_format_events_voice_empty(self):
        mock_service = MagicMock()
        mock_service.events.return_value.list.return_value.execute.return_value = {"items": []}

        client = _make_client(mock_service)
        result = client.list_events_voice("2025-06-10", "2025-06-10")

        assert result == "No events found."

    def test_availability_voice_friendly(self):
        mock_service = MagicMock()
        mock_service.freebusy.return_value.query.return_value.execute.return_value = {
            "calendars": {
                "primary": {
                    "busy": [{"start": "2025-06-10T10:00:00Z", "end": "2025-06-10T11:00:00Z"}]
                }
            }
        }

        client = _make_client(mock_service)
        result = client.availability_voice("2025-06-10")

        assert "9:00 am" in result
        assert "10:00 am" in result
        assert "11:00 am" in result
        assert "5:00 pm" in result
