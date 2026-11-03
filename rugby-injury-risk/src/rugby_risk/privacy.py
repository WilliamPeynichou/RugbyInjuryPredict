import hashlib
import hmac

from rugby_risk.errors import PrivacyViolationError
from rugby_risk.settings import get_settings


def player_key(player_id: int, salt: str | None = None) -> str:
    """Pseudonym: HMAC-SHA256(player_id, salt)[:16 hex]. Empty salt refused outside env `test`."""
    settings = get_settings()
    secret = salt if salt is not None else settings.pseudonym_salt.get_secret_value()
    if not secret and settings.env != "test":
        raise PrivacyViolationError("PSEUDONYM_SALT is empty")
    return hmac.new(secret.encode(), str(player_id).encode(), hashlib.sha256).hexdigest()[:16]
