from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum


class CallStatus(Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ProposedAction:
    tool: str
    description: str
    params: dict


@dataclass
class CallRecord:
    call_id: str
    to_number: str
    instructions: str
    status: CallStatus
    started_at: float
    context: dict | None = None
    transcript: list[dict] = field(default_factory=list)
    summary: str = ""
    proposed_actions: list[ProposedAction] = field(default_factory=list)
    duration_seconds: int = 0
    transferred: bool = False
    voicemail: bool = False
    error: str | None = None


class CallManager:
    def __init__(self) -> None:
        self._calls: dict[str, CallRecord] = {}

    def create_call(
        self,
        to_number: str,
        instructions: str,
        context: dict | None = None,
    ) -> str:
        call_id = f"call_{uuid.uuid4().hex[:12]}"
        self._calls[call_id] = CallRecord(
            call_id=call_id,
            to_number=to_number,
            instructions=instructions,
            status=CallStatus.IN_PROGRESS,
            started_at=time.time(),
            context=context,
        )
        return call_id

    def get_call(self, call_id: str) -> CallRecord | None:
        return self._calls.get(call_id)

    def complete_call(
        self,
        call_id: str,
        transcript: list[dict],
        summary: str,
        proposed_actions: list[dict | ProposedAction],
        duration_seconds: int,
        transferred: bool = False,
        voicemail: bool = False,
    ) -> None:
        call = self._calls[call_id]
        call.status = CallStatus.COMPLETED
        call.transcript = transcript
        call.summary = summary
        call.transferred = transferred
        call.voicemail = voicemail
        call.proposed_actions = [
            a if isinstance(a, ProposedAction) else ProposedAction(**a)
            for a in proposed_actions
        ]
        call.duration_seconds = duration_seconds

    def fail_call(self, call_id: str, error: str) -> None:
        call = self._calls[call_id]
        call.status = CallStatus.FAILED
        call.error = error

    def list_active_calls(self) -> list[CallRecord]:
        return [c for c in self._calls.values() if c.status == CallStatus.IN_PROGRESS]
