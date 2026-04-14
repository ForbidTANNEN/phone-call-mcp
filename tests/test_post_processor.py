import json
import pytest
from unittest.mock import AsyncMock, patch
from dial_mcp.post_processor import extract_actions, build_extraction_prompt


class TestBuildExtractionPrompt:
    def test_builds_prompt_with_transcript(self):
        transcript = [
            {"role": "agent", "text": "Hi, I'm calling to reschedule an appointment."},
            {"role": "human", "text": "Sure, how about Friday at 3pm?"},
            {"role": "agent", "text": "Friday at 3pm works. I'll get that confirmed for you."},
        ]
        prompt = build_extraction_prompt(transcript)
        assert "reschedule" in prompt
        assert "Friday at 3pm" in prompt
        assert "agent:" in prompt.lower() or "Agent:" in prompt

    def test_includes_json_schema_instruction(self):
        transcript = [{"role": "agent", "text": "Hello"}]
        prompt = build_extraction_prompt(transcript)
        assert "proposed_actions" in prompt
        assert "summary" in prompt


class TestExtractActions:
    @pytest.mark.asyncio
    async def test_parses_llm_response(self):
        mock_response = json.dumps({
            "summary": "Patient rescheduled to Friday 3pm",
            "proposed_actions": [
                {
                    "tool": "calendar.update_event",
                    "description": "Move appointment to Friday 3pm",
                    "params": {"event_id": "evt_123", "new_time": "2026-04-18T15:00:00"},
                }
            ],
        })

        mock_client = AsyncMock()
        mock_client.messages.create.return_value = AsyncMock(
            content=[AsyncMock(text=mock_response)]
        )

        transcript = [
            {"role": "agent", "text": "I'll reschedule that."},
            {"role": "human", "text": "Friday 3pm please."},
        ]

        with patch("dial_mcp.post_processor.anthropic.AsyncAnthropic", return_value=mock_client):
            result = await extract_actions(transcript, api_key="test-key")

        assert result["summary"] == "Patient rescheduled to Friday 3pm"
        assert len(result["proposed_actions"]) == 1
        assert result["proposed_actions"][0]["tool"] == "calendar.update_event"

    @pytest.mark.asyncio
    async def test_handles_no_actions(self):
        mock_response = json.dumps({
            "summary": "Left a voicemail, no answer.",
            "proposed_actions": [],
        })

        mock_client = AsyncMock()
        mock_client.messages.create.return_value = AsyncMock(
            content=[AsyncMock(text=mock_response)]
        )

        transcript = [{"role": "agent", "text": "No answer, leaving voicemail."}]

        with patch("dial_mcp.post_processor.anthropic.AsyncAnthropic", return_value=mock_client):
            result = await extract_actions(transcript, api_key="test-key")

        assert result["proposed_actions"] == []
