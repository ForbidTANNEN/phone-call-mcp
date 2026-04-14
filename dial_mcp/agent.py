from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections.abc import AsyncIterable
from datetime import datetime

import aiohttp
from livekit import api, rtc
from livekit.agents import Agent, AgentSession, JobContext
from livekit.agents.llm.mcp import MCPServerHTTP, MCPServerStdio
from livekit.agents.utils import http_context
from livekit.plugins.anthropic import LLM as AnthropicLLM
from livekit.plugins.cartesia import TTS as CartesiaTTS
from livekit.plugins.deepgram import STT as DeepgramSTT
from livekit.plugins.silero import VAD as SileroVAD

from dial_mcp.call_manager import CallManager
from dial_mcp.config import Config, MCPServerConfig
from dial_mcp.post_processor import extract_actions
from dial_mcp.tool_filter import filter_write_tools

logger = logging.getLogger("dial-mcp.agent")


# ─── Base voice prompt ───────────────────────────────────────────────
# Defines HOW to be a voice agent. Goes FIRST, before goal instructions.
# Kept short — every token adds latency on every LLM turn.
VOICE_BASE_PROMPT = """You are a voice assistant on a live phone call. A text-to-speech engine speaks every word you output. You are not a chatbot.

RULES:
- Only output words the caller should hear. Nothing else.
- Never output: asterisks, stage directions, tone descriptions, markdown, bullet points, brackets, parentheses around actions. Never describe how you sound. Never narrate actions.
- 1 to 2 sentences per turn max. Then stop and let them speak.
- One question at a time. Never stack questions.
- Lists: say 2 or 3 items in a natural sentence. Ask if they want more. Never dump a full list.
- Call tools silently. Do not announce lookups. Just do it and speak the result.
- Times: say "ten thirty" not "10:30". Dates: say "Tuesday April fourteenth" not "04/14".
- No filler words. No "um" or "uh". No repeated pleasantries.
- If you can't hear: "Sorry, I didn't catch that."
- If they say "hold on": wait silently.
- Be warm and helpful. Acknowledge what they say. Vary your phrasing.
"""


# ─── Tool result processing ──────────────────────────────────────────
# Transforms raw MCP tool results into voice-friendly text BEFORE the LLM.
# This is critical: the LLM should never see URLs, HTML, emails, or raw JSON.

def _clean_tool_result(ctx) -> str | None:
    """Transform MCP tool results into clean, voice-friendly text.

    Calendar events come back with HTML descriptions, attendee emails,
    Google Meet URLs, long event IDs, etc. If any of that reaches the LLM,
    it leaks into speech as 'dot dot dot' or technical garbage.

    This function strips all non-voice-safe content so the LLM only sees
    clean event names, times, and attendee first names.
    """
    result = ctx.result
    if not isinstance(result, str):
        return None

    # Try to parse as JSON and extract just what matters
    try:
        data = json.loads(result)
        if isinstance(data, dict) and "events" in data:
            return _format_calendar_events(data)
    except (json.JSONDecodeError, TypeError):
        pass

    # Fallback: regex clean raw text
    cleaned = result
    cleaned = re.sub(r'<[^>]+>', ' ', cleaned)          # HTML tags
    cleaned = re.sub(r'https?://[^\s<>"\']+', '', cleaned)  # URLs
    cleaned = re.sub(r'[\w.+-]+@[\w-]+\.[\w.-]+', '', cleaned)  # emails
    cleaned = re.sub(r'[a-f0-9]{16,}', '', cleaned)     # hex IDs
    cleaned = re.sub(r'"[^"]{50,}"', '', cleaned)        # long quoted strings
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


def _format_calendar_events(data: dict) -> str:
    """Convert calendar API response into a short voice-friendly summary."""
    events = data.get("events", [])
    if not events:
        return "No events found for that time period."

    lines = []
    for ev in events:
        summary = ev.get("summary", "Untitled event")
        start = ev.get("start", {})

        if ev.get("allDay"):
            lines.append(f"All day: {summary}")
            continue

        start_dt = start.get("dateTime", "")
        if start_dt:
            try:
                dt = datetime.fromisoformat(start_dt)
                time_str = dt.strftime("%-I:%M %p").lower()
                lines.append(f"{time_str}: {summary}")
            except ValueError:
                lines.append(summary)
        else:
            lines.append(summary)

    return "Events:\n" + "\n".join(lines)


# ─── MCP server construction ────────────────────────────────────────

def build_mcp_servers(
    mcp_configs: list[MCPServerConfig],
) -> list[MCPServerHTTP | MCPServerStdio]:
    servers = []
    for cfg in mcp_configs:
        if cfg.url:
            servers.append(MCPServerHTTP(
                url=cfg.url,
                tool_result_resolver=_clean_tool_result,
            ))
        elif cfg.command:
            servers.append(MCPServerStdio(
                command=cfg.command,
                args=cfg.args,
                env=cfg.env or None,
                tool_result_resolver=_clean_tool_result,
            ))
        else:
            logger.warning(f"MCP server '{cfg.name}' has no url or command, skipping")
    return servers


# ─── Agent ───────────────────────────────────────────────────────────

class PhoneCallAgent(Agent):
    def __init__(self, instructions: str) -> None:
        super().__init__(instructions=instructions)
        self._greeting_sent = False

    async def on_enter(self) -> None:
        pass  # greeting sent after SIP participant answers

    def send_greeting(self) -> None:
        if not self._greeting_sent:
            self._greeting_sent = True
            self.session.generate_reply()


# ─── Call runner ─────────────────────────────────────────────────────

async def run_call(
    config: Config,
    call_id: str,
    to_number: str,
    instructions: str,
    call_manager: CallManager,
    context: dict | None = None,
    vad: SileroVAD | None = None,
    extra_mcp_urls: list[str] | None = None,
) -> None:
    """Create a LiveKit room, dial out, and run the voice agent."""
    _http_session = aiohttp.ClientSession()
    http_context._ContextVar.set(lambda: _http_session)

    try:
        # Merge config-level MCP servers with per-call servers from orchestrator
        mcp_servers = build_mcp_servers(config.mcp_servers)
        for url in (extra_mcp_urls or []):
            mcp_servers.append(MCPServerHTTP(url=url, tool_result_resolver=_clean_tool_result))

        now = datetime.now()
        current_date = now.strftime("%A, %B %d, %Y")
        current_time = now.strftime("%I:%M %p")

        # Base prompt (HOW) + date + goal prompt (WHAT)
        agent_instructions = f"""{VOICE_BASE_PROMPT}
Today is {current_date}. The current time is {current_time}.

YOUR TASK FOR THIS CALL:
{instructions}"""

        if context:
            agent_instructions += f"\n\nCONTEXT:\n{context}"

        agent = PhoneCallAgent(instructions=agent_instructions)

        session = AgentSession(
            stt=DeepgramSTT(
                api_key=config.deepgram.api_key,
                model="nova-3",
                no_delay=True,
                endpointing_ms=25,
                smart_format=True,
                filler_words=True,
            ),
            llm=AnthropicLLM(
                model=config.anthropic.model,
                api_key=config.anthropic.api_key,
                temperature=0.7,
            ),
            tts=CartesiaTTS(
                api_key=config.cartesia.api_key,
                speed=0.9,
            ),
            vad=vad or SileroVAD.load(
                min_silence_duration=0.4,
                activation_threshold=0.5,
                prefix_padding_duration=0.3,
            ),
            turn_handling={
                "turn_detection": "vad",
                "endpointing": {
                    "mode": "dynamic",
                    "min_delay": 0.3,
                    "max_delay": 1.5,
                },
                "interruption": {
                    "enabled": True,
                    "mode": "adaptive",
                    "min_duration": 0.5,
                    "min_words": 1,
                    "resume_false_interruption": True,
                },
            },
            tts_text_transforms=["filter_markdown", "filter_emoji"],
            mcp_servers=mcp_servers,
            max_tool_steps=5,
            preemptive_generation=True,
        )

        # Collect transcript
        transcript: list[dict] = []
        call_start = time.time()

        @session.on("conversation_item_added")
        def on_item(ev):
            item = ev.item
            if hasattr(item, "role") and hasattr(item, "text_content"):
                if item.text_content:
                    role = "agent" if item.role == "assistant" else "human"
                    transcript.append({"role": role, "text": item.text_content})

        # Create room and dial out
        async with api.LiveKitAPI(
            url=config.livekit.url,
            api_key=config.livekit.api_key,
            api_secret=config.livekit.api_secret,
        ) as lk:
            room_name = f"phone-call-{call_id}"

            await lk.room.create_room(
                api.CreateRoomRequest(name=room_name, empty_timeout=300)
            )

            room = rtc.Room()
            token = (
                api.AccessToken(config.livekit.api_key, config.livekit.api_secret)
                .with_identity("phone-agent")
                .with_grants(api.VideoGrants(room_join=True, room=room_name))
                .to_jwt()
            )
            await room.connect(config.livekit.url, token)
            await session.start(agent=agent, room=room)

            # Dial out
            await lk.sip.create_sip_participant(
                api.CreateSIPParticipantRequest(
                    sip_trunk_id=config.twilio.sip_trunk_id,
                    sip_call_to=to_number,
                    room_name=room_name,
                    participant_identity="phone-user",
                    participant_name="Phone User",
                    play_dialtone=True,
                    wait_until_answered=True,
                ),
                timeout=30,
            )

            # Person answered — send greeting after brief audio settling
            await asyncio.sleep(0.5)
            agent.send_greeting()

            # Wait for hangup
            disconnected = False

            @room.on("participant_disconnected")
            def on_disconnect(participant: rtc.RemoteParticipant):
                nonlocal disconnected
                if participant.identity == "phone-user":
                    disconnected = True

            while not disconnected:
                await asyncio.sleep(1)

            duration = int(time.time() - call_start)

            # Post-process with Sonnet (better quality, latency doesn't matter here)
            if transcript:
                try:
                    result = await extract_actions(
                        transcript=transcript,
                        api_key=config.anthropic.api_key,
                        model="claude-sonnet-4-20250514",
                    )
                    summary = result.get("summary", "")
                    proposed_actions = result.get("proposed_actions", [])
                except Exception as e:
                    logger.warning(f"Post-processing failed: {e}")
                    summary = "Post-processing failed"
                    proposed_actions = []
            else:
                summary = "No conversation recorded"
                proposed_actions = []

            call_manager.complete_call(
                call_id=call_id,
                transcript=transcript,
                summary=summary,
                proposed_actions=proposed_actions,
                duration_seconds=duration,
            )

            await room.disconnect()

    except Exception as e:
        logger.error(f"Call {call_id} failed: {e}")
        call_manager.fail_call(call_id, error=str(e))
    finally:
        await _http_session.close()
