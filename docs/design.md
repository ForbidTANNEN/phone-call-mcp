# dial-mcp Design Spec

**Date:** 2026-04-11 **Status:** Draft

## Overview

An open-source MCP server that gives any AI agent the ability to make phone calls where the voice agent on the call can read from the same MCP tools the orchestrator has access to.

Every other phone-call MCP is a black box — you pass a prompt, it talks, you get a transcript. This one gives the voice agent your tools. It can check calendars, look up records, and verify information mid-call in real-time.

**Primary use case:** OpenClaw instances and personal agents that need phone capabilities with tool access.

## Key Decisions

- **Scope (v1):** Outbound calls only. User provides their own Twilio credentials. No phone number provisioning or inbound call handling.
- **Voice LLM:** Anthropic Sonnet 4.6 via STT → LLM → TTS pipeline (not realtime streaming).
- **STT:** Deepgram (configurable).
- **TTS:** Cartesia (configurable).
- **Voice framework:** LiveKit Agents (Python). Chosen for native MCP client support — the voice agent connects to MCP servers directly, no reimplementation of integrations.
- **Read-only on the call:** The voice agent can only read from MCP tools during the call. All writes happen post-call by the orchestrator.
- **Post-call structured output:** The voice agent extracts proposed actions as structured JSON. The orchestrator reviews and executes.
- **Standalone open-source project.** Published to PyPI, usable by anyone. Clean for community adoption.

## MCP Tools (Exposed to Orchestrator)

### `make_call`

| Param | Type | Required | Description |
| --- | --- | --- | --- |
| `to_number` | string (E.164) | yes | Phone number to call |
| `instructions` | string | yes | What the voice agent should do on the call |
| `context` | object | no | Structured data the voice agent should know (patient name, appointment details, etc.) |

Returns `call_id` immediately. The call runs async.

### `get_call_result`

| Param | Type | Required | Description |
| --- | --- | --- | --- |
| `call_id` | string | yes | The call to check |

Returns:

```json
{
  "call_id": "call_abc123",
  "status": "completed",
  "duration_seconds": 142,
  "transcript": [
    {"role": "agent", "text": "Hi, I'm calling from Dr. Smith's office..."},
    {"role": "human", "text": "Oh yes, I need to reschedule..."}
  ],
  "summary": "Patient requested to move Thursday 2pm appointment to Friday 3pm. Confirmed Friday 3pm works.",
  "proposed_actions": [
    {
      "tool": "calendar.update_event",
      "description": "Reschedule appointment to Friday 3pm",
      "params": {
        "event_id": "evt_123",
        "new_time": "2026-04-18T15:00:00"
      },
      "status": "pending"
    }
  ]
}
```

Status values: `in_progress`, `completed`, `failed`.

### `list_active_calls`

No params. Returns array of active call IDs with status and start time.

## Architecture

```
Orchestrator (Claude/OpenClaw)
    │
    │  MCP tool call: make_call(to_number, instructions, context)
    ▼
┌─────────────────────────────┐
│  dial-mcp server      │
│  (Python, runs as MCP)      │
│                             │
│  1. Creates LiveKit Room    │
│  2. Connects Twilio SIP     │
│     trunk to the room       │
│  3. Spins up Agent Session: │
│     ├── STT: Deepgram       │
│     ├── LLM: Sonnet 4.6     │
│     ├── TTS: Cartesia       │
│     └── MCP clients (read)  │
│         ├── calendar         │
│         ├── crm              │
│         └── ...              │
│  4. Dials the number        │
└─────────────────────────────┘
    │                ▲
    │ audio          │ audio
    ▼                │
┌─────────────┐     │
│  LiveKit     │─────┘
│  Cloud/Server│
└─────────────┘
    │        ▲
    │ SIP    │ SIP
    ▼        │
┌─────────────┐
│  Twilio      │
│  SIP Trunk   │
└─────────────┘
    │        ▲
    │ PSTN   │ PSTN
    ▼        │
   Phone
```

### Call Lifecycle

1. Orchestrator calls `make_call` → gets `call_id` back immediately
2. Server creates a LiveKit room, attaches Twilio SIP trunk, dials the number
3. Person picks up → audio flows through Twilio → LiveKit → Agent
4. Agent hears speech (Deepgram STT), thinks (Sonnet 4.6 + read-only MCP tools), speaks (Cartesia TTS)
5. Call ends (hangup or agent decides it's done)
6. Post-processing: agent extracts structured actions from the conversation
7. Orchestrator calls `get_call_result` → gets transcript + actions + summary

### Read-Only Filtering (v1)

When the server starts, for each configured MCP server:

1. Connect and call `tools/list`
2. Filter out tools whose names match write patterns: `create`, `update`, `delete`, `write`, `send`, `post`, `put`, `patch`, `remove`, `add`, `set`, `modify`
3. Pass remaining tool names as `allowed_tools` to LiveKit's MCP server config

v2 will add per-server `allowed_tools` and `blocked_tools` config overrides.

### No Double-Write Guarantee

The voice agent is read-only — it cannot write to any MCP server during the call. It only proposes actions in the post-call structured output. The orchestrator is the sole executor of writes. No deduplication needed in v1.

**v2 note:** If write capabilities are added to the voice agent later, proposed actions will include `"executed_on_call": true` so the orchestrator skips them.

## Configuration

```yaml
# Telephony
twilio:
  account_sid: "AC..."
  auth_token: "..."
  phone_number: "+14155551234"

# LiveKit
livekit:
  url: "wss://your-project.livekit.cloud"
  api_key: "..."
  api_secret: "..."

# LLM (voice agent brain)
anthropic:
  api_key: "sk-ant-..."
  model: "claude-sonnet-4-6-20250514"

# Speech
deepgram:
  api_key: "..."

cartesia:
  api_key: "..."

# MCP servers the voice agent can read from during calls
mcp_servers:
  - name: "calendar"
    url: "http://localhost:8001/sse"
  - name: "crm"
    command: "npx"
    args: ["some-crm-mcp"]
    env:
      API_KEY: "..."
```

All config values can also be set via environment variables (e.g. `TWILIO_ACCOUNT_SID`). YAML takes precedence when both are set.

MCP servers support both HTTP/SSE (`url` field) and stdio (`command` + `args` fields).

The MCP server itself runs in two modes:

- **stdio (default):** For Claude Code and local clients. `command: "python", args: ["-m", "dial_mcp"]`
- **HTTP/SSE:** For remote clients. `python -m dial_mcp --serve --port 8080`

## Project Structure

```
dial-mcp/
├── pyproject.toml
├── README.md
├── LICENSE (MIT)
├── dial_mcp/
│   ├── __init__.py
│   ├── server.py          # MCP server (tools: make_call, get_call_result, list_active_calls)
│   ├── agent.py           # LiveKit Agent definition (instructions, MCP wiring)
│   ├── call_manager.py    # Manages active calls, lifecycle, stores results
│   ├── tool_filter.py     # Read-only filtering logic (connect → list tools → whitelist)
│   ├── post_processor.py  # Extract structured actions from transcript
│   └── config.py          # Load/validate YAML config + env vars
├── config.example.yaml
└── docs/
    └── setup.md
```

## LiveKit Implementation Details

Based on LiveKit Agents SDK v1.4+:

- **MCP servers** pass to `AgentSession(mcp_servers=[...])`. Both `mcp.MCPServerHTTP` and `mcp.MCPServerStdio` are supported.
- **Tool filtering** uses `allowed_tools` parameter on each MCP server instance.
- **Anthropic LLM** via `livekit.plugins.anthropic.LLM(model="claude-sonnet-4-6-20250514")`.
- **Outbound calls** require Twilio Elastic SIP Trunking (not TwiML Bin — that's inbound only).
- **MCP server failures are non-blocking** — if one server is down, the agent starts with whatever connected.
- `max_tool_steps` defaults to 3 per turn. May need increasing for complex lookup chains.
- `tool_result_resolver` (v1.4.5+) can trim large MCP responses before they reach the LLM — useful for keeping voice agent focused.

## Future (v2+)

- Inbound call handling (reception desk use case)
- Phone number provisioning via Twilio API
- Per-server `allowed_tools` / `blocked_tools` config
- Selective write access with `executed_on_call` deduplication
- Hosted SaaS version (same codebase, user just provides Anthropic key)
- Configurable LLM provider (OpenAI, Gemini, etc.)