"""Encryption utilities for secure data storage."""

from __future__ import annotations

import base64
import os

from cryptography.fernet import Fernet


class EncryptionService:
    """Service for encrypting/decrypting sensitive data."""

    def __init__(self, key: str | bytes | None = None):
        """Initialize with encryption key.

        Args:
        ----
            key: Encryption key as string, bytes, or None.
                 If None, will use env variable or generate new.

        """
        if key is not None:
            # Convert to bytes if needed
            key_bytes: bytes = key.encode() if isinstance(key, str) else key
            self.fernet = Fernet(key_bytes)
        else:
            # Generate key from environment variable or create new
            env_key = os.getenv("ENCRYPTION_KEY")
            if not env_key:
                env_key = Fernet.generate_key().decode()
                print(f"Generated new encryption key: {env_key}")
                print("Add this to your .env file as ENCRYPTION_KEY")
            self.fernet = Fernet(env_key.encode())

    def encrypt(self, data: str) -> str:
        """Encrypt a string and return base64 encoded result."""
        if not data:
            raise ValueError("Cannot encrypt empty data")

        encrypted = self.fernet.encrypt(data.encode())
        return base64.b64encode(encrypted).decode()

    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt base64 encoded data and return original string."""
        if not encrypted_data:
            raise ValueError("Cannot decrypt empty data")

        try:
            decoded = base64.b64decode(encrypted_data.encode())
            decrypted = self.fernet.decrypt(decoded)
            return decrypted.decode()
        except Exception as e:
            raise ValueError(f"Decryption failed: {str(e)}") from e

    @staticmethod
    def generate_key() -> str:
        """Generate a new Fernet encryption key."""
        return Fernet.generate_key().decode()


# Global encryption service instance
encryption_service = EncryptionService()
