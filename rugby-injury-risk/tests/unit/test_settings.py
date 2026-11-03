from pathlib import Path

import pytest
from pydantic import ValidationError

from rugby_risk.settings import Settings, get_settings

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    for field in Settings.model_fields:
        monkeypatch.delenv(field.upper(), raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_defaults_and_secrets():
    settings = Settings(pseudonym_salt="private-salt", llm_api_key="private-key")
    assert settings.env == "dev"
    assert settings.data_dir == Path("data")
    assert "private-salt" not in repr(settings)
    assert "private-key" not in repr(settings)


def test_dotenv_and_yaml(tmp_path):
    (tmp_path / ".env").write_text("ENV=test\nHTTP_CONTACT=dotenv@example.com\n")
    (tmp_path / "config").mkdir()
    (tmp_path / "config/settings.test.yaml").write_text("http_contact: yaml\nllm_model: example\n")
    settings = get_settings()
    assert settings.http_contact == "dotenv@example.com"
    assert settings.llm_model == "example"


def test_environment_overrides_dotenv(monkeypatch, tmp_path):
    (tmp_path / ".env").write_text("HTTP_CONTACT=dotenv@example.com\n")
    monkeypatch.setenv("HTTP_CONTACT", "env@example.com")
    assert get_settings().http_contact == "env@example.com"


def test_no_yaml_and_cache(monkeypatch):
    settings = get_settings()
    monkeypatch.setenv("HTTP_CONTACT", "changed")
    assert get_settings() is settings
    get_settings.cache_clear()
    assert get_settings().http_contact == "changed"


@pytest.mark.parametrize("content", ["", "[]", "- invalid"])
def test_yaml_content(tmp_path, content):
    (tmp_path / "config").mkdir()
    (tmp_path / "config/settings.dev.yaml").write_text(content)
    if content:
        with pytest.raises(ValueError, match="Expected a mapping"):
            get_settings()
    else:
        assert get_settings().env == "dev"


def test_invalid_environment(monkeypatch):
    monkeypatch.setenv("ENV", "invalid")
    with pytest.raises(ValidationError):
        get_settings()
