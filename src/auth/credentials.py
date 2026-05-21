"""Secure token storage and retrieval for SEM Master.

Primary storage: OS keyring (via keyring library).
Fallback storage: Fernet-encrypted file at ~/.sem-master/credentials/tokens.enc.

The Fernet encryption key is itself stored in the keyring; if keyring is
unavailable, the key is written to ~/.sem-master/credentials/.keyfile with
restricted permissions.
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import keyring
import keyring.errors
from cryptography.fernet import Fernet, InvalidToken
from google.oauth2.credentials import Credentials

from src.auth import StorageError
from src.utils.config_manager import CONFIG_DIR

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------
SERVICE_NAME = "sem-master"
TOKEN_USERNAME = "oauth-tokens"
TOKEN_FILE = CONFIG_DIR / "credentials" / "tokens.enc"
KEY_FILE = CONFIG_DIR / "credentials" / ".keyfile"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_or_create_key() -> bytes:
    """Retrieve or generate the Fernet encryption key.

    Tries the keyring first; falls back to a file on disk.

    Returns:
        Raw Fernet key bytes.
    """
    # Try to load from keyring
    try:
        stored = keyring.get_password(SERVICE_NAME, "fernet-key")
        if stored is not None:
            return base64.urlsafe_b64decode(stored)
    except Exception:
        pass  # Keyring unavailable — fall through to file

    # Try to load from file
    if KEY_FILE.exists():
        try:
            raw = KEY_FILE.read_bytes().strip()
            return base64.urlsafe_b64decode(raw)
        except Exception:
            pass  # Corrupt key file — generate a new one

    # Generate a fresh key
    key = Fernet.generate_key()
    encoded = base64.urlsafe_b64encode(key).decode()

    # Try to persist in keyring
    try:
        keyring.set_password(SERVICE_NAME, "fernet-key", encoded)
        logger.debug("Fernet key stored in OS keyring")
        return key
    except Exception:
        pass  # Keyring unavailable — write to file

    # Persist to file
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    KEY_FILE.write_bytes(base64.urlsafe_b64encode(key))
    try:
        KEY_FILE.chmod(0o600)
    except Exception:
        pass  # Windows — chmod is a no-op; file is already in user's home dir
    logger.debug("Fernet key stored in file: %s", KEY_FILE)
    return key


def _credentials_to_dict(credentials: Credentials) -> dict:
    """Serialize a Credentials object to a plain dict.

    Args:
        credentials: Google OAuth Credentials object.

    Returns:
        Dict with token, refresh_token, token_uri, client_id, client_secret, expiry.
    """
    expiry_str: str | None = None
    if credentials.expiry is not None:
        expiry_str = credentials.expiry.isoformat()

    return {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "expiry": expiry_str,
    }


def _dict_to_credentials(data: dict) -> Credentials:
    """Deserialize a dict back into a Credentials object.

    Args:
        data: Dict produced by _credentials_to_dict.

    Returns:
        Reconstructed google.oauth2.credentials.Credentials.
    """
    expiry: datetime | None = None
    if data.get("expiry"):
        expiry = datetime.fromisoformat(data["expiry"])
        # google.oauth2.credentials.Credentials.expiry is naive UTC by convention.
        # Its .expired check compares against _helpers.utcnow() which is naive,
        # so a tz-aware value here triggers TypeError on comparison.
        if expiry.tzinfo is not None:
            expiry = expiry.astimezone(timezone.utc).replace(tzinfo=None)

    return Credentials(
        token=data.get("token"),
        refresh_token=data.get("refresh_token"),
        token_uri=data.get("token_uri"),
        client_id=data.get("client_id"),
        client_secret=data.get("client_secret"),
        expiry=expiry,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def store_tokens(credentials: Credentials) -> None:
    """Persist OAuth tokens securely.

    Tries the OS keyring first; falls back to a Fernet-encrypted file.

    Args:
        credentials: Valid google.oauth2.credentials.Credentials to store.

    Raises:
        StorageError: If both keyring and file storage fail.
    """
    data = _credentials_to_dict(credentials)
    json_str = json.dumps(data)

    # Primary: keyring
    try:
        keyring.set_password(SERVICE_NAME, TOKEN_USERNAME, json_str)
        logger.debug("Tokens stored in OS keyring")
        return
    except Exception as e:
        logger.debug("Keyring storage failed (%s); falling back to encrypted file", e)

    # Fallback: Fernet-encrypted file
    try:
        key = _get_or_create_key()
        f = Fernet(key)
        encrypted = f.encrypt(json_str.encode())
        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_FILE.write_bytes(encrypted)
        logger.debug("Tokens stored in encrypted file: %s", TOKEN_FILE)
    except Exception as e:
        raise StorageError(f"Failed to store tokens in both keyring and file: {e}") from e


def load_tokens() -> Credentials | None:
    """Load OAuth tokens from secure storage.

    Tries the OS keyring first; falls back to the Fernet-encrypted file.

    Returns:
        Reconstructed Credentials, or None if no tokens are stored or the
        stored data is corrupt/unreadable.
    """
    # Primary: keyring
    try:
        json_str = keyring.get_password(SERVICE_NAME, TOKEN_USERNAME)
        if json_str is not None:
            try:
                data = json.loads(json_str)
                logger.debug("Tokens loaded from OS keyring")
                return _dict_to_credentials(data)
            except Exception as e:
                logger.warning("Corrupt token data in keyring: %s", e)
    except Exception as e:
        logger.debug("Keyring read failed (%s); trying encrypted file", e)

    # Fallback: encrypted file
    if TOKEN_FILE.exists():
        try:
            key = _get_or_create_key()
            f = Fernet(key)
            encrypted = TOKEN_FILE.read_bytes()
            json_str = f.decrypt(encrypted).decode()
            data = json.loads(json_str)
            logger.debug("Tokens loaded from encrypted file: %s", TOKEN_FILE)
            return _dict_to_credentials(data)
        except (InvalidToken, json.JSONDecodeError, Exception) as e:
            logger.warning("Could not decrypt/parse token file: %s", e)

    return None


def clear_tokens() -> None:
    """Remove all stored tokens and encryption keys from all backends.

    Silently ignores errors so this always completes even if some backends
    are unavailable.
    """
    # Clear tokens from keyring
    try:
        keyring.delete_password(SERVICE_NAME, TOKEN_USERNAME)
        logger.debug("Tokens removed from OS keyring")
    except Exception:
        pass

    # Clear Fernet key from keyring
    try:
        keyring.delete_password(SERVICE_NAME, "fernet-key")
        logger.debug("Fernet key removed from OS keyring")
    except Exception:
        pass

    # Remove token file
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
        logger.debug("Token file removed: %s", TOKEN_FILE)

    # Remove key file
    if KEY_FILE.exists():
        KEY_FILE.unlink()
        logger.debug("Key file removed: %s", KEY_FILE)
