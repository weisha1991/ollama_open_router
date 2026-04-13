import os
import pytest
from ollama_router.config import (
    Config,
    load_config,
    expand_env,
    is_likely_api_key,
    get_key_id,
)


def test_config_dataclass():
    config = Config(
        listen="127.0.0.1:11435",
        upstream="https://ollama.com/v1",
        keys=["key1", "key2"],
        cooldown_session_hours=72,
        cooldown_rate_hours=4,
    )
    assert config.listen == "127.0.0.1:11435"
    assert config.upstream == "https://ollama.com/v1"
    assert len(config.keys) == 2


def test_config_from_yaml(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
listen: "127.0.0.1:11435"
upstream: "https://ollama.com/v1"
keys:
  - "test_key_1"
  - "test_key_2"
cooldown:
  session_limit_hours: 72
  rate_limit_hours: 4
"""
    )
    config = load_config(str(config_file))
    assert config.listen == "127.0.0.1:11435"
    assert len(config.keys) == 2


def test_expand_env_with_var_set(monkeypatch):
    monkeypatch.setenv("TEST_API_KEY", "my-secret-key")
    assert expand_env("${TEST_API_KEY}") == "my-secret-key"


def test_expand_env_with_var_not_set():
    assert expand_env("${NONEXISTENT_VAR_12345}") is None


def test_expand_env_plain_string():
    assert expand_env("just-a-string") == "just-a-string"


def test_is_likely_api_key_hardcoded():
    assert is_likely_api_key("a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6.xYzAbC123") is True


def test_is_likely_api_key_env_var_ref():
    assert is_likely_api_key("${OLLAMA_API_KEY}") is False


def test_is_likely_api_key_env_name():
    assert is_likely_api_key("MY_API_KEY") is False


def test_is_likely_api_key_empty():
    assert is_likely_api_key("") is False


def test_is_likely_api_key_short():
    assert is_likely_api_key("short") is False


def test_get_key_id():
    id1 = get_key_id("my-api-key")
    id2 = get_key_id("another-key")
    assert len(id1) == 8
    assert id1 != id2


def test_get_key_id_empty():
    assert get_key_id("") == "empty"


def test_get_key_id_consistent():
    id1 = get_key_id("my-api-key")
    id2 = get_key_id("my-api-key")
    assert id1 == id2


def test_load_config_no_keys(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
listen: "127.0.0.1:11435"
upstream: "https://ollama.com/v1"
keys: []
"""
    )
    with pytest.raises(ValueError, match="No valid API keys"):
        load_config(str(config_file))


def test_load_config_env_var_keys(monkeypatch, tmp_path):
    monkeypatch.setenv("MY_KEY_1", "actual-key-1")
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
keys:
  - "${MY_KEY_1}"
"""
    )
    config = load_config(str(config_file))
    assert config.keys == ["actual-key-1"]


def test_load_config_hardcoded_key_warns(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
keys:
   - "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6.xYzAbC123"
"""
    )
    with pytest.warns(UserWarning, match="Security warning"):
        load_config(str(config_file))


def test_logging_config_defaults():
    from ollama_router.config import LoggingConfig

    config = LoggingConfig()
    assert config.level == "INFO"
    assert config.file is None
    assert config.max_size_mb == 10
    assert config.backup_count == 5


def test_logging_config_from_dict():
    from ollama_router.config import LoggingConfig

    config = LoggingConfig(
        level="DEBUG",
        file="logs/test.log",
        max_size_mb=20,
        backup_count=3,
    )
    assert config.level == "DEBUG"
    assert config.file == "logs/test.log"
    assert config.max_size_mb == 20
    assert config.backup_count == 3


def test_logging_config_in_main_config(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
listen: "127.0.0.1:11435"
upstream: "https://ollama.com/v1"
keys:
  - "test_key_1"
logging:
  level: "DEBUG"
  file: "logs/app.log"
  max_size_mb: 20
  backup_count: 3
"""
    )
    config = load_config(str(config_file))
    assert config.logging.level == "DEBUG"
    assert config.logging.file == "logs/app.log"
    assert config.logging.max_size_mb == 20
    assert config.logging.backup_count == 3


def test_logging_config_env_var_override(monkeypatch, tmp_path):
    monkeypatch.setenv("OLLAMA_LOG_LEVEL", "ERROR")
    monkeypatch.setenv("OLLAMA_LOG_FILE", "/var/log/ollama.log")
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
listen: "127.0.0.1:11435"
upstream: "https://ollama.com/v1"
keys:
  - "test_key_1"
logging:
  level: "DEBUG"
  file: "logs/app.log"
"""
    )
    config = load_config(str(config_file))
    assert config.logging.level == "ERROR"
    assert config.logging.file == "/var/log/ollama.log"


def test_logging_config_defaults_when_not_specified(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
listen: "127.0.0.1:11435"
upstream: "https://ollama.com/v1"
keys:
  - "test_key_1"
"""
    )
    config = load_config(str(config_file))
    assert config.logging.level == "INFO"
    assert config.logging.file is None
    assert config.logging.max_size_mb == 10
    assert config.logging.backup_count == 5
