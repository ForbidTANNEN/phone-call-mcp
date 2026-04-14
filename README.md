# dial-mcp

An MCP server that gives AI agents the ability to make phone calls with real-time tool access.

Every other phone-call MCP is a black box — you pass a prompt, it talks, you get a transcript. **This one gives the voice agent your tools.** It can check calendars, look up records, and verify information mid-call.

```
Your AI Agent (Claude, OpenClaw, etc.)
    ├── Calendar MCP
    ├── CRM MCP
    └── dial-mcp  ← this project
          │
          │  make_call("+15551234567", "Reschedule the appointment...")
          │
          ▼
        Voice Agent (on the phone call)
          ├── Hears: "How about Thursday at 3pm?"
          ├── Checks: Calendar MCP → Thursday 3pm is available
          └── Says: "Thursday at 3pm works, I'll get that confirmed."
```

The voice agent reads from your MCP servers during the call. After the call, it returns a transcript and proposed actions for your agent to execute.

## Quick Start

### 1. Install

```bash
pip install dial-mcp
```

### 2. Set up credentials

```bash
dial-mcp init
```

This walks you through connecting 5 services (all have free tiers):

| Service | What it does | Sign up |
|---------|-------------|---------|
| [Twilio](https://www.twilio.com/try-twilio) | Telephony — makes the actual phone calls | Free trial |
| [LiveKit](https://cloud.livekit.io) | Voice infrastructure — rooms and audio routing | Free tier |
| [Anthropic](https://console.anthropic.com) | LLM — the voice agent's brain | Pay-as-you-go |
| [Deepgram](https://deepgram.com) | Speech-to-text | Free tier |
| [Cartesia](https://cartesia.ai) | Text-to-speech | Free tier |

### 3. Start the server

```bash
dial-mcp serve
```

### 4. Connect to your agent

**Claude Code:**
```bash
claude mcp add --transport sse phone-calls http://localhost:8080/sse
```

**claude_desktop_config.json / claude.json:**
```json
{
  "mcpServers": {
    "phone-calls": {
      "command": "dial-mcp",
      "args": ["--config", "config.yaml"]
    }
  }
}
```

**OpenClaw / other agents:**
```bash
# Any MCP client that supports SSE:
http://localhost:8080/sse
```

That's it. Your agent now has `make_call`, `get_call_result`, and `list_active_calls` tools.

## Tools

### `make_call`

Make an outbound phone call. Returns a `call_id` immediately — the call runs async.

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `to_number` | string | yes | Phone number in E.164 format (`+15551234567`) |
| `instructions` | string | yes | What the voice agent should do on the call |
| `context` | object | no | Structured data for the voice agent |
| `mcp_servers` | string[] | no | HTTP URLs of MCP servers to connect during the call |

### `get_call_result`

Get transcript, summary, and proposed actions when a call completes.

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `call_id` | string | yes | The call ID from `make_call` |

Returns:
```json
{
  "status": "completed",
  "transcript": [
    {"role": "agent", "text": "Hi, I'm calling about your appointment..."},
    {"role": "human", "text": "Sure, how about Friday at 3?"}
  ],
  "summary": "Rescheduled appointment to Friday 3pm.",
  "proposed_actions": [
    {
      "tool": "calendar.update_event",
      "description": "Move appointment to Friday 3pm",
      "params": {"event_id": "evt_123", "new_time": "2026-04-18T15:00:00"}
    }
  ]
}
```

### `list_active_calls`

List all currently active calls. No params.

## Giving the Voice Agent Your Tools

The real power is connecting MCP servers so the voice agent can look things up mid-call. Add them to `config.yaml`:

```yaml
mcp_servers:
  - name: "calendar"
    url: "http://localhost:8001/sse"

  - name: "crm"
    command: "npx"
    args: ["some-crm-mcp-server"]
    env:
      API_KEY: "your_key"
```

Or pass them per-call via the `mcp_servers` parameter on `make_call`.

The voice agent gets **read-only access** — write operations (`create`, `update`, `delete`, etc.) are automatically filtered out. After the call, proposed writes are returned as `proposed_actions` for your orchestrator to execute.

## Configuration

All values in `config.yaml` can also be set via environment variables:

| Env Var | Config Key |
|---------|-----------|
| `TWILIO_ACCOUNT_SID` | `twilio.account_sid` |
| `TWILIO_AUTH_TOKEN` | `twilio.auth_token` |
| `TWILIO_PHONE_NUMBER` | `twilio.phone_number` |
| `LIVEKIT_SIP_TRUNK_ID` | `twilio.sip_trunk_id` |
| `LIVEKIT_URL` | `livekit.url` |
| `LIVEKIT_API_KEY` | `livekit.api_key` |
| `LIVEKIT_API_SECRET` | `livekit.api_secret` |
| `ANTHROPIC_API_KEY` | `anthropic.api_key` |
| `DEEPGRAM_API_KEY` | `deepgram.api_key` |
| `CARTESIA_API_KEY` | `cartesia.api_key` |

YAML values take precedence over env vars.

## Architecture

- **Voice LLM:** Claude (Haiku by default, configurable)
- **STT:** Deepgram Nova 3
- **TTS:** Cartesia Sonic 2
- **Voice Framework:** [LiveKit Agents](https://docs.livekit.io/agents/) with native MCP support
- **Telephony:** Twilio SIP Trunk → LiveKit

## Twilio + LiveKit SIP Setup

You need a Twilio Elastic SIP Trunk connected to LiveKit. Here's the short version:

1. **LiveKit:** Go to Cloud Console → SIP → Create Outbound Trunk. Copy the trunk ID (`ST_...`).
2. **Twilio:** Create an Elastic SIP Trunk → set the Origination URI to the one LiveKit gives you.
3. **Twilio:** Buy a phone number and assign it to the SIP trunk.

See [LiveKit SIP docs](https://docs.livekit.io/home/telephony/overview/) for detailed setup.

## License

MIT
