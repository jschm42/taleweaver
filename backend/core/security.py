import logging

from cryptography.fernet import Fernet

from backend.core.config import settings

logger = logging.getLogger(__name__)

class EncryptionUtil:
    def __init__(self):
        key = settings.ENCRYPTION_KEY
        if not key or not str(key).strip():
            raise RuntimeError(
                "ENCRYPTION_KEY is not configured. Generate one with "
                "`python scripts/generate_fernet_key.py` and set it in your .env file. "
                "Refusing to start: persisting API keys without a stable key would make "
                "them unreadable after the next restart."
            )
        try:
            self._fernet = Fernet(str(key).encode('utf-8'))
        except Exception as e:
            logger.error(f"Failed to initialize Fernet with provided key: {e}")
            raise ValueError("Invalid ENCRYPTION_KEY format. Must be a valid 32-byte base64-encoded string.") from e

    def encrypt_key(self, plain_key: str) -> str:
        """Encrypt a plain text API key."""
        if not plain_key:
            return ""
        encrypted = self._fernet.encrypt(plain_key.encode('utf-8'))
        return encrypted.decode('utf-8')

    def decrypt_key(self, encrypted_key: str) -> str:
        """Decrypt an encrypted API key."""
        if not encrypted_key:
            return ""
        try:
            decrypted = self._fernet.decrypt(encrypted_key.encode('utf-8'))
            return decrypted.decode('utf-8')
        except Exception as e:
            logger.error(f"Failed to decrypt key: {e}")
            raise ValueError(
                "Failed to decrypt stored API key. The ENCRYPTION_KEY in .env may have changed since the key was saved."
            ) from e

# Global instance for easy usage
encryption_util = EncryptionUtil()
