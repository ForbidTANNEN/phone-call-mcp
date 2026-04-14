from __future__ import annotations

from pathlib import Path

import yaml

REQUIRED_SERVICES = [
    {
        "name": "Twilio",
        "description": "Telephony — makes the actual phone calls via SIP",
        "signup_url": "https://www.twilio.com/try-twilio",
        "fields": [
            ("twilio_account_sid", "Account SID", "Starts with AC..."),
            ("twilio_auth_token", "Auth Token", ""),
            ("twilio_phone_number", "Phone Number", "E.164 format, e.g. +15551234567"),
            ("twilio_sip_trunk_id", "SIP Trunk ID", "LiveKit outbound trunk, starts with ST_..."),
        ],
    },
    {
        "name": "LiveKit",
        "description": "Voice infrastructure — rooms, audio routing, agent framework",
        "signup_url": "https://cloud.livekit.io",
        "fields": [
            ("livekit_url", "Server URL", "e.g. wss://your-project.livekit.cloud"),
            ("livekit_api_key", "API Key", ""),
            ("livekit_api_secret", "API Secret", ""),
        ],
    },
    {
        "name": "Anthropic",
        "description": "LLM — the voice agent's brain",
        "signup_url": "https://console.anthropic.com",
        "fields": [
            ("anthropic_api_key", "API Key", "Starts with sk-ant-..."),
        ],
    },
    {
        "name": "Deepgram",
        "description": "Speech-to-text — converts caller audio to text",
        "signup_url": "https://deepgram.com",
        "fields": [
            ("deepgram_api_key", "API Key", ""),
        ],
    },
    {
        "name": "Cartesia",
        "description": "Text-to-speech — gives the agent a voice",
        "signup_url": "https://cartesia.ai",
        "fields": [
            ("cartesia_api_key", "API Key", ""),
        ],
    },
]


def build_config_from_answers(answers: dict[str, str]) -> dict:
    return {
        "twilio": {
            "account_sid": answers["twilio_account_sid"],
            "auth_token": answers["twilio_auth_token"],
            "phone_number": answers["twilio_phone_number"],
            "sip_trunk_id": answers["twilio_sip_trunk_id"],
        },
        "livekit": {
            "url": answers["livekit_url"],
            "api_key": answers["livekit_api_key"],
            "api_secret": answers["livekit_api_secret"],
        },
        "anthropic": {
            "api_key": answers["anthropic_api_key"],
            "model": "claude-haiku-4-5-20251001",
        },
        "deepgram": {
            "api_key": answers["deepgram_api_key"],
        },
        "cartesia": {
            "api_key": answers["cartesia_api_key"],
        },
        "mcp_servers": [],
    }


def write_config(config: dict, path: str, force: bool = False) -> None:
    output = Path(path)
    if output.exists() and not force:
        raise FileExistsError(f"{path} already exists. Use --force to overwrite.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)


def run_init(output_path: str = "config.yaml", force: bool = False) -> None:
    print("\ndial-mcp setup wizard")
    print("=" * 40)
    print("You'll need accounts with the following services.\n")

    answers: dict[str, str] = {}

    for service in REQUIRED_SERVICES:
        print(f"\n--- {service['name']} ---")
        print(f"  {service['description']}")
        print(f"  Sign up: {service['signup_url']}")

        for key, label, hint in service["fields"]:
            prompt = f"  {label}"
            if hint:
                prompt += f" ({hint})"
            prompt += ": "
            value = input(prompt).strip()
            answers[key] = value

    config = build_config_from_answers(answers)

    try:
        write_config(config, output_path, force=force)
    except FileExistsError as e:
        print(f"\nError: {e}")
        return

    print(f"\nConfig written to {output_path}")
    print("\nNext steps:")
    print("  1. Add MCP servers to config.yaml (optional — calendar, CRM, etc.)")
    print("  2. Start the server:  dial-mcp serve")
    print("  3. Add to your agent:")
    print("     claude mcp add --transport sse phone-calls http://localhost:8080/sse")
    print()
