from cryptography.fernet import Fernet
from backend.core.config import settings
import logging

logger = logging.getLogger(__name__)

class EncryptionUtil:
    def __init__(self):
        try:
            self._fernet = Fernet(settings.ENCRYPTION_KEY.encode('utf-8'))
        except Exception as e:
            logger.error(f"Failed to initialize Fernet with provided key: {e}")
            raise ValueError("Invalid ENCRYPTION_KEY format. Must be a valid 32-byte base64-encoded string.")

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
        decrypted = self._fernet.decrypt(encrypted_key.encode('utf-8'))
        return decrypted.decode('utf-8')

# Global instance for easy usage
encryption_util = EncryptionUtil()
