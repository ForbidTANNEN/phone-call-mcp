import pytest
import yaml
from pathlib import Path
from dial_mcp.init import build_config_from_answers, write_config, REQUIRED_SERVICES


class TestBuildConfig:
    def test_builds_minimal_config(self):
        answers = {
            "twilio_account_sid": "AC_test",
            "twilio_auth_token": "tok_test",
            "twilio_phone_number": "+15551234567",
            "twilio_sip_trunk_id": "ST_test",
            "livekit_url": "wss://test.livekit.cloud",
            "livekit_api_key": "key_test",
            "livekit_api_secret": "secret_test",
            "anthropic_api_key": "sk-ant-test",
            "deepgram_api_key": "dg_test",
            "cartesia_api_key": "cart_test",
        }
        config = build_config_from_answers(answers)
        assert config["twilio"]["account_sid"] == "AC_test"
        assert config["livekit"]["url"] == "wss://test.livekit.cloud"
        assert config["anthropic"]["api_key"] == "sk-ant-test"
        assert config["anthropic"]["model"] == "claude-haiku-4-5-20251001"
        assert config["deepgram"]["api_key"] == "dg_test"
        assert config["cartesia"]["api_key"] == "cart_test"
        assert config["mcp_servers"] == []


class TestWriteConfig:
    def test_writes_yaml_file(self, tmp_path):
        config = {
            "twilio": {"account_sid": "AC_test"},
            "livekit": {"url": "wss://test.livekit.cloud"},
        }
        output = tmp_path / "config.yaml"
        write_config(config, str(output))
        loaded = yaml.safe_load(output.read_text())
        assert loaded["twilio"]["account_sid"] == "AC_test"

    def test_does_not_overwrite_existing(self, tmp_path):
        output = tmp_path / "config.yaml"
        output.write_text("existing: true")
        with pytest.raises(FileExistsError):
            write_config({"twilio": {}}, str(output))

    def test_force_overwrites_existing(self, tmp_path):
        output = tmp_path / "config.yaml"
        output.write_text("existing: true")
        write_config({"twilio": {"account_sid": "new"}}, str(output), force=True)
        loaded = yaml.safe_load(output.read_text())
        assert loaded["twilio"]["account_sid"] == "new"


class TestRequiredServices:
    def test_all_services_listed(self):
        names = [s["name"] for s in REQUIRED_SERVICES]
        assert "Twilio" in names
        assert "LiveKit" in names
        assert "Anthropic" in names
        assert "Deepgram" in names
        assert "Cartesia" in names
