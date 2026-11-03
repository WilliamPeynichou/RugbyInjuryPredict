import pytest

from rugby_risk.errors import PrivacyViolationError
from rugby_risk.privacy import player_key
from rugby_risk.settings import get_settings


@pytest.fixture(autouse=True)
def clean(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.delenv("PSEUDONYM_SALT", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


pytestmark = pytest.mark.unit
KEY_LEN = 16


def test_deterministic_and_salted():
    assert player_key(1, "a") == player_key(1, "a")
    assert player_key(1, "a") != player_key(1, "b")
    assert player_key(1, "a") != player_key(2, "a")
    assert len(player_key(1, "a")) == KEY_LEN


def test_salt_from_settings(monkeypatch):
    monkeypatch.setenv("PSEUDONYM_SALT", "s")
    assert player_key(1) == player_key(1, "s")


def test_empty_salt_refused_in_dev():
    with pytest.raises(PrivacyViolationError):
        player_key(1)


def test_empty_salt_allowed_in_test(monkeypatch):
    monkeypatch.setenv("ENV", "test")
    assert len(player_key(1)) == KEY_LEN
