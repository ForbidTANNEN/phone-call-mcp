import os
import pytest
import tempfile
import yaml
from dial_mcp.config import load_config, Config, MCPServerConfig


class TestLoadConfigFromYaml:
    def test_loads_full_config(self, tmp_path):
        config_data = {
            "twilio": {
                "account_sid": "AC_test",
                "auth_token": "test_token",
                "phone_number": "+15551234567",
                "sip_trunk_id": "ST_test",
            },
            "livekit": {
                "url": "wss://test.livekit.cloud",
                "api_key": "key123",
                "api_secret": "secret123",
            },
            "anthropic": {
                "api_key": "sk-ant-test",
                "model": "claude-haiku-4-5-20251001",
            },
            "deepgram": {"api_key": "dg_test"},
            "cartesia": {"api_key": "cart_test"},
            "mcp_servers": [
                {"name": "calendar", "url": "http://localhost:8001/sse"},
                {
                    "name": "crm",
                    "command": "npx",
                    "args": ["some-crm-mcp"],
                    "env": {"API_KEY": "crm_key"},
                },
            ],
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_data))

        config = load_config(str(config_file))

        assert config.twilio.account_sid == "AC_test"
        assert config.twilio.phone_number == "+15551234567"
        assert config.livekit.url == "wss://test.livekit.cloud"
        assert config.anthropic.model == "claude-haiku-4-5-20251001"
        assert len(config.mcp_servers) == 2
        assert config.mcp_servers[0].name == "calendar"
        assert config.mcp_servers[0].url == "http://localhost:8001/sse"
        assert config.mcp_servers[1].name == "crm"
        assert config.mcp_servers[1].command == "npx"
        assert config.mcp_servers[1].args == ["some-crm-mcp"]
        assert config.mcp_servers[1].env == {"API_KEY": "crm_key"}


class TestLoadConfigFromEnv:
    def test_env_vars_fill_missing_yaml(self, tmp_path, monkeypatch):
        config_data = {
            "livekit": {
                "url": "wss://test.livekit.cloud",
                "api_key": "key123",
                "api_secret": "secret123",
            },
            "mcp_servers": [],
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_data))

        monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC_env")
        monkeypatch.setenv("TWILIO_AUTH_TOKEN", "token_env")
        monkeypatch.setenv("TWILIO_PHONE_NUMBER", "+15559999999")
        monkeypatch.setenv("LIVEKIT_SIP_TRUNK_ID", "ST_env")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-env")
        monkeypatch.setenv("DEEPGRAM_API_KEY", "dg_env")
        monkeypatch.setenv("CARTESIA_API_KEY", "cart_env")

        config = load_config(str(config_file))

        assert config.twilio.account_sid == "AC_env"
        assert config.twilio.phone_number == "+15559999999"
        assert config.anthropic.api_key == "sk-ant-env"
        assert config.anthropic.model == "claude-haiku-4-5-20251001"

    def test_yaml_takes_precedence_over_env(self, tmp_path, monkeypatch):
        config_data = {
            "twilio": {
                "account_sid": "AC_yaml",
                "auth_token": "token_yaml",
                "phone_number": "+15551111111",
            },
            "livekit": {
                "url": "wss://test.livekit.cloud",
                "api_key": "key123",
                "api_secret": "secret123",
            },
            "anthropic": {"api_key": "sk-ant-yaml"},
            "deepgram": {"api_key": "dg_yaml"},
            "cartesia": {"api_key": "cart_yaml"},
            "mcp_servers": [],
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_data))

        monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC_env")

        config = load_config(str(config_file))
        assert config.twilio.account_sid == "AC_yaml"


class TestConfigDefaults:
    def test_default_model(self, tmp_path):
        config_data = {
            "twilio": {
                "account_sid": "AC_test",
                "auth_token": "test_token",
                "phone_number": "+15551234567",
                "sip_trunk_id": "ST_test",
            },
            "livekit": {
                "url": "wss://test.livekit.cloud",
                "api_key": "key123",
                "api_secret": "secret123",
            },
            "anthropic": {"api_key": "sk-ant-test"},
            "deepgram": {"api_key": "dg_test"},
            "cartesia": {"api_key": "cart_test"},
            "mcp_servers": [],
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_data))

        config = load_config(str(config_file))
        assert config.anthropic.model == "claude-haiku-4-5-20251001"
