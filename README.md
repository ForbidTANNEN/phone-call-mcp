# dial-mcp

Give your AI agent the ability to make phone calls — with real-time tool access.

```
pip install dial-mcp && dial-mcp init && dial-mcp serve
```

Then add to your agent:

```bash
claude mcp add --transport sse phone-calls http://localhost:8080/sse
```

Your agent now has a `make_call` tool. It can call real phone numbers, talk to people, and use your other MCP tools (calendar, CRM, etc.) during the conversation.

---

## What makes this different

Every other phone-call MCP is a black box — you pass a prompt, it talks, you get a transcript.

**dial-mcp gives the voice agent your tools.** Mid-call, it can check calendars, look up records, and verify information in real-time. After the call, it returns proposed actions for your agent to execute.

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

## Setup

### 1. Install

```bash
pip install dial-mcp
```

### 2. Create accounts (all have free tiers)

You need API keys from 5 services. The setup wizard links you to each:

| Service | What it does | Free tier |
|---------|-------------|-----------|
| [Twilio](https://www.twilio.com/try-twilio) | Makes the actual phone calls via SIP | Trial credit |
| [LiveKit](https://cloud.livekit.io) | Voice infrastructure — rooms & audio routing | Free |
| [Anthropic](https://console.anthropic.com) | LLM — the voice agent's brain | Pay-as-you-go |
| [Deepgram](https://deepgram.com) | Speech-to-text | Free tier |
| [Cartesia](https://cartesia.ai) | Text-to-speech | Free tier |

You'll also need to set up a **Twilio Elastic SIP Trunk** connected to LiveKit. See [SIP setup](#twilio--livekit-sip-setup) below.

### 3. Run the setup wizard

```bash
dial-mcp init
```

This prompts you for each API key and saves them locally to `config.yaml`. Your keys never leave your machine.

### 4. Start the server

```bash
dial-mcp serve
```

This starts an MCP server at `http://localhost:8080/sse`.

### 5. Connect to your agent

**Claude Code:**
```bash
claude mcp add --transport sse phone-calls http://localhost:8080/sse
```

**Claude Desktop / claude.json:**
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

**OpenClaw / any MCP client:**
```
http://localhost:8080/sse
```

Done. Your agent can now make phone calls.

---

## Tools

Your agent gets three tools:

### `make_call`

Make an outbound phone call. Returns a `call_id` immediately — the call runs in the background.

```
make_call(
  to_number="+15551234567",
  instructions="You are calling on behalf of Dr. Smith's office to reschedule Jane's appointment.",
  mcp_servers=["http://localhost:8001/sse"]  # optional: give the voice agent your calendar, CRM, etc.
)
```

### `get_call_result`

Check on a call. Once complete, returns the full transcript, a summary, and proposed actions:

```json
{
  "status": "completed",
  "transcript": [
    {"role": "agent", "text": "Hi, I'm calling from Dr. Smith's office about your appointment."},
    {"role": "human", "text": "Oh yes, can we move it to Friday at 3?"}
  ],
  "summary": "Patient requested to reschedule to Friday 3pm. Confirmed availability.",
  "proposed_actions": [
    {
      "tool": "calendar.update_event",
      "description": "Move appointment to Friday 3pm",
      "params": {"event_id": "evt_123", "new_time": "2026-04-18T15:00:00"}
    }
  ]
}
```

The voice agent proposes actions but never executes writes. Your orchestrator reviews and runs them.

### `list_active_calls`

List all calls currently in progress.

---

## Giving the voice agent your tools

The real power is connecting MCP servers so the voice agent can look things up mid-call.

**Option A: In config.yaml** (always available)
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

**Option B: Per-call** (passed by the orchestrator)
```
make_call(
  to_number="+15551234567",
  instructions="...",
  mcp_servers=["http://localhost:8001/sse", "http://localhost:8002/sse"]
)
```

The voice agent gets **read-only access** — write operations (`create`, `update`, `delete`, etc.) are automatically filtered out.

---

## Configuration

`dial-mcp init` creates a `config.yaml` with your API keys. You can also use environment variables:

| Env Var | What it is |
|---------|-----------|
| `TWILIO_ACCOUNT_SID` | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | Twilio auth token |
| `TWILIO_PHONE_NUMBER` | Your Twilio phone number |
| `LIVEKIT_SIP_TRUNK_ID` | LiveKit SIP trunk ID |
| `LIVEKIT_URL` | LiveKit server URL |
| `LIVEKIT_API_KEY` | LiveKit API key |
| `LIVEKIT_API_SECRET` | LiveKit API secret |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `DEEPGRAM_API_KEY` | Deepgram API key |
| `CARTESIA_API_KEY` | Cartesia API key |

YAML values take precedence over env vars.

---

## Twilio + LiveKit SIP Setup

You need a Twilio Elastic SIP Trunk connected to LiveKit for outbound calls:

1. **LiveKit Cloud Console** → SIP → Create Outbound Trunk → copy the trunk ID (`ST_...`)
2. **Twilio Console** → Elastic SIP Trunking → Create trunk → set Origination URI to the one LiveKit provides
3. **Twilio Console** → Buy a phone number → assign it to the SIP trunk

Full guide: [LiveKit SIP docs](https://docs.livekit.io/home/telephony/overview/)

---

## Architecture

- **Voice LLM:** Claude (Haiku by default, configurable)
- **Speech-to-Text:** Deepgram Nova 3
- **Text-to-Speech:** Cartesia Sonic 2
- **Voice Framework:** [LiveKit Agents](https://docs.livekit.io/agents/) with native MCP support
- **Telephony:** Twilio SIP Trunk → LiveKit Cloud

## License

MIT
