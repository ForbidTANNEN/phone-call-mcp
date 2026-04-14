from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class TwilioConfig:
    account_sid: str
    auth_token: str
    phone_number: str
    sip_trunk_id: str


@dataclass
class LiveKitConfig:
    url: str
    api_key: str
    api_secret: str


@dataclass
class AnthropicConfig:
    api_key: str
    model: str = "claude-haiku-4-5-20251001"


@dataclass
class DeepgramConfig:
    api_key: str


@dataclass
class CartesiaConfig:
    api_key: str


@dataclass
class MCPServerConfig:
    name: str
    url: str | None = None
    command: str | None = None
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class Config:
    twilio: TwilioConfig
    livekit: LiveKitConfig
    anthropic: AnthropicConfig
    deepgram: DeepgramConfig
    cartesia: CartesiaConfig
    mcp_servers: list[MCPServerConfig] = field(default_factory=list)


def load_config(config_path: str) -> Config:
    with open(config_path) as f:
        data = yaml.safe_load(f) or {}

    twilio_data = data.get("twilio", {})
    livekit_data = data.get("livekit", {})
    anthropic_data = data.get("anthropic", {})
    deepgram_data = data.get("deepgram", {})
    cartesia_data = data.get("cartesia", {})

    twilio = TwilioConfig(
        account_sid=twilio_data.get("account_sid") or os.environ.get("TWILIO_ACCOUNT_SID", ""),
        auth_token=twilio_data.get("auth_token") or os.environ.get("TWILIO_AUTH_TOKEN", ""),
        phone_number=twilio_data.get("phone_number") or os.environ.get("TWILIO_PHONE_NUMBER", ""),
        sip_trunk_id=twilio_data.get("sip_trunk_id") or os.environ.get("LIVEKIT_SIP_TRUNK_ID", ""),
    )

    livekit = LiveKitConfig(
        url=livekit_data.get("url") or os.environ.get("LIVEKIT_URL", ""),
        api_key=livekit_data.get("api_key") or os.environ.get("LIVEKIT_API_KEY", ""),
        api_secret=livekit_data.get("api_secret") or os.environ.get("LIVEKIT_API_SECRET", ""),
    )

    anthropic = AnthropicConfig(
        api_key=anthropic_data.get("api_key") or os.environ.get("ANTHROPIC_API_KEY", ""),
        model=anthropic_data.get("model", "claude-haiku-4-5-20251001"),
    )

    deepgram = DeepgramConfig(
        api_key=deepgram_data.get("api_key") or os.environ.get("DEEPGRAM_API_KEY", ""),
    )

    cartesia = CartesiaConfig(
        api_key=cartesia_data.get("api_key") or os.environ.get("CARTESIA_API_KEY", ""),
    )

    mcp_servers = []
    for srv in data.get("mcp_servers", []):
        mcp_servers.append(MCPServerConfig(
            name=srv["name"],
            url=srv.get("url"),
            command=srv.get("command"),
            args=srv.get("args", []),
            env=srv.get("env", {}),
        ))

    return Config(
        twilio=twilio,
        livekit=livekit,
        anthropic=anthropic,
        deepgram=deepgram,
        cartesia=cartesia,
        mcp_servers=mcp_servers,
    )
