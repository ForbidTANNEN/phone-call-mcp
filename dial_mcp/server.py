from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict

from mcp.server import Server
from mcp.types import Tool, TextContent

from dial_mcp.call_manager import CallManager, CallStatus
from dial_mcp.config import Config
from dial_mcp.calendar.credentials import discover_google_credentials
from dial_mcp.calendar.oauth import run_oauth_flow

logger = logging.getLogger("dial-mcp.server")


def create_mcp_server(config: Config, call_manager: CallManager) -> Server:
    server = Server("dial-mcp")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="make_call",
                description=(
                    "Make an outbound phone call with an AI voice agent. Returns a call_id "
                    "immediately — use get_call_result to check status and transcript.\n\n"
                    "The voice agent ALREADY has Google Calendar access built in — it can "
                    "check events, availability, and schedules in real-time during the call. "
                    "You do NOT need to pass calendar URLs or pre-fetch calendar data. Just "
                    "describe what the call should accomplish in the instructions and the "
                    "voice agent handles the rest.\n\n"
                    "IMPORTANT — instructions: Be specific about who the caller is and what "
                    "the voice agent should do. Include names, relevant details, and the "
                    "goal of the call. The voice agent follows these as its system prompt."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "to_number": {
                            "type": "string",
                            "description": "Phone number to call in E.164 format (e.g. +15551234567)",
                        },
                        "instructions": {
                            "type": "string",
                            "description": (
                                "System prompt for the voice agent. Be specific: include who the "
                                "caller is (name, email, account ID), the goal of the call, and any "
                                "relevant context. Example: 'You are calling on behalf of John Smith "
                                "(john@example.com). Check his calendar for availability this week "
                                "and schedule a follow-up appointment.'"
                            ),
                        },
                        "mcp_servers": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "HTTP/SSE URLs of MCP servers the voice agent should connect to "
                                "during the call (read-only access). Pass any MCP servers you have "
                                "that would be useful on the call — calendar, CRM, patient records, "
                                "etc. Example: [\"http://localhost:8001/mcp\", \"http://localhost:8002/sse\"]"
                            ),
                        },
                        "context": {
                            "type": "object",
                            "description": (
                                "Optional structured data the voice agent should know. Useful for "
                                "passing patient details, appointment info, or other structured "
                                "context that supplements the instructions."
                            ),
                        },
                    },
                    "required": ["to_number", "instructions"],
                },
            ),
            Tool(
                name="get_call_result",
                description=(
                    "Get the result of a phone call. Returns status, transcript, "
                    "summary, and proposed actions when the call is complete."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "call_id": {
                            "type": "string",
                            "description": "The call ID returned by make_call",
                        },
                    },
                    "required": ["call_id"],
                },
            ),
            Tool(
                name="list_active_calls",
                description="List all currently active phone calls.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="list_integrations",
                description=(
                    "Check which integrations are connected (e.g. Google Calendar). "
                    "Call this before make_call if the call involves scheduling or appointments. "
                    "If Google Calendar is not linked, call link_calendar first to connect it."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="link_calendar",
                description=(
                    "Link a Google Calendar account so the voice agent can access it during calls. "
                    "Opens a browser window for OAuth authentication."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "provider": {
                            "type": "string",
                            "enum": ["google"],
                            "description": "Calendar provider to link. Currently only 'google' is supported.",
                        },
                    },
                    "required": ["provider"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        if name == "make_call":
            return await handle_make_call(config, call_manager, arguments)
        elif name == "get_call_result":
            return await handle_get_call_result(call_manager, arguments)
        elif name == "list_active_calls":
            return await handle_list_active_calls(call_manager)
        elif name == "list_integrations":
            return await handle_list_integrations()
        elif name == "link_calendar":
            return await handle_link_calendar(arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    return server


async def handle_make_call(
    config: Config,
    call_manager: CallManager,
    arguments: dict,
) -> list[TextContent]:
    to_number = arguments["to_number"]
    instructions = arguments["instructions"]
    context = arguments.get("context")
    call_mcp_servers = arguments.get("mcp_servers", [])

    # Validate E.164 format
    if not to_number.startswith("+") or not to_number[1:].isdigit():
        return [TextContent(
            type="text",
            text=json.dumps({"error": "Phone number must be in E.164 format (e.g. +15551234567)"}),
        )]

    call_id = call_manager.create_call(
        to_number=to_number,
        instructions=instructions,
        context=context,
    )

    # Launch the call in the background
    from dial_mcp.agent import run_call
    asyncio.create_task(run_call(
        config=config,
        call_id=call_id,
        to_number=to_number,
        instructions=instructions,
        call_manager=call_manager,
        context=context,
        extra_mcp_urls=call_mcp_servers,
    ))

    return [TextContent(
        type="text",
        text=json.dumps({
            "call_id": call_id,
            "status": "in_progress",
            "message": f"Call initiated to {to_number}. Use get_call_result with this call_id to check status.",
        }),
    )]


async def handle_get_call_result(
    call_manager: CallManager,
    arguments: dict,
) -> list[TextContent]:
    call_id = arguments["call_id"]
    call = call_manager.get_call(call_id)

    if call is None:
        return [TextContent(
            type="text",
            text=json.dumps({"error": f"Call {call_id} not found"}),
        )]

    result = {
        "call_id": call.call_id,
        "status": call.status.value,
        "to_number": call.to_number,
    }

    if call.status == CallStatus.COMPLETED:
        result.update({
            "duration_seconds": call.duration_seconds,
            "transcript": call.transcript,
            "summary": call.summary,
            "proposed_actions": [
                {"tool": a.tool, "description": a.description, "params": a.params}
                for a in call.proposed_actions
            ],
        })
    elif call.status == CallStatus.FAILED:
        result["error"] = call.error
    elif call.status == CallStatus.IN_PROGRESS:
        result["message"] = "Call is still in progress. Try again in a few moments."

    return [TextContent(type="text", text=json.dumps(result))]


async def handle_list_active_calls(call_manager: CallManager) -> list[TextContent]:
    active = call_manager.list_active_calls()
    calls = [
        {
            "call_id": c.call_id,
            "to_number": c.to_number,
            "status": c.status.value,
            "started_at": c.started_at,
        }
        for c in active
    ]
    return [TextContent(type="text", text=json.dumps({"active_calls": calls}))]


async def handle_list_integrations() -> list[TextContent]:
    creds = discover_google_credentials()
    if creds is not None:
        google_calendar = {"status": "linked", "source": creds.source}
    else:
        google_calendar = {
            "status": "not_linked",
            "action": "Call link_calendar with provider='google' to connect Google Calendar.",
        }
    return [TextContent(type="text", text=json.dumps({"google_calendar": google_calendar}))]


async def handle_link_calendar(arguments: dict) -> list[TextContent]:
    provider = arguments.get("provider")
    if provider != "google":
        return [TextContent(
            type="text",
            text=json.dumps({"error": f"Unsupported provider: {provider!r}. Only 'google' is currently supported."}),
        )]

    creds = discover_google_credentials()
    if creds is not None:
        return [TextContent(
            type="text",
            text=json.dumps({"status": "already_linked", "source": creds.source}),
        )]

    try:
        run_oauth_flow()
        return [TextContent(
            type="text",
            text=json.dumps({"status": "linked", "message": "Google Calendar successfully linked."}),
        )]
    except Exception as exc:
        return [TextContent(
            type="text",
            text=json.dumps({"status": "failed", "error": str(exc)}),
        )]


