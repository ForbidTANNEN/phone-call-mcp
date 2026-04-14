import pytest
from dial_mcp.call_manager import CallManager, CallStatus


class TestCallManager:
    def test_create_call(self):
        mgr = CallManager()
        call_id = mgr.create_call(
            to_number="+15551234567",
            instructions="Schedule an appointment",
        )
        assert call_id.startswith("call_")
        call = mgr.get_call(call_id)
        assert call.to_number == "+15551234567"
        assert call.instructions == "Schedule an appointment"
        assert call.status == CallStatus.IN_PROGRESS

    def test_create_call_with_context(self):
        mgr = CallManager()
        call_id = mgr.create_call(
            to_number="+15551234567",
            instructions="Schedule an appointment",
            context={"patient": "John Smith", "date": "Thursday"},
        )
        call = mgr.get_call(call_id)
        assert call.context == {"patient": "John Smith", "date": "Thursday"}

    def test_complete_call(self):
        mgr = CallManager()
        call_id = mgr.create_call(to_number="+15551234567", instructions="Test")
        mgr.complete_call(
            call_id=call_id,
            transcript=[
                {"role": "agent", "text": "Hello"},
                {"role": "human", "text": "Hi"},
            ],
            summary="Brief test call",
            proposed_actions=[],
            duration_seconds=30,
        )
        call = mgr.get_call(call_id)
        assert call.status == CallStatus.COMPLETED
        assert call.duration_seconds == 30
        assert len(call.transcript) == 2
        assert call.summary == "Brief test call"

    def test_fail_call(self):
        mgr = CallManager()
        call_id = mgr.create_call(to_number="+15551234567", instructions="Test")
        mgr.fail_call(call_id, error="Connection timeout")
        call = mgr.get_call(call_id)
        assert call.status == CallStatus.FAILED
        assert call.error == "Connection timeout"

    def test_list_active_calls(self):
        mgr = CallManager()
        id1 = mgr.create_call(to_number="+15551111111", instructions="Call 1")
        id2 = mgr.create_call(to_number="+15552222222", instructions="Call 2")
        mgr.complete_call(id1, transcript=[], summary="", proposed_actions=[], duration_seconds=10)

        active = mgr.list_active_calls()
        assert len(active) == 1
        assert active[0].call_id == id2

    def test_get_nonexistent_call(self):
        mgr = CallManager()
        assert mgr.get_call("call_nonexistent") is None
