import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
from typing import Optional

class EncryptionService:
    """Service for encrypting/decrypting sensitive data like wallet secrets"""
    
    def __init__(self, key: Optional[str] = None):
        """Initialize with encryption key from settings or generate new"""
        if key:
            # Ensure key is properly formatted
            if isinstance(key, str):
                try:
                    # Try to use the key directly if it's valid base64
                    self.fernet = Fernet(key.encode() if len(key) == 44 else key)
                except Exception:
                    # If not valid, generate from the string
                    self.fernet = Fernet(self._derive_key_from_string(key))
            else:
                self.fernet = Fernet(key)
        else:
            # Generate new key if none provided
            key = Fernet.generate_key()
            self.fernet = Fernet(key)
            print(f"⚠️ Generated new encryption key: {key.decode()}")
            print("Add this to your .env file as ENCRYPTION_KEY")
    
    def _derive_key_from_string(self, password: str) -> bytes:
        """Derive a valid Fernet key from any string"""
        salt = b'xrp-telegram-bot-salt'  # Fixed salt for consistency
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key
    
    def encrypt(self, data: str) -> str:
        """Encrypt a string and return base64 encoded result"""
        if not data:
            raise ValueError("Cannot encrypt empty data")
        
        encrypted = self.fernet.encrypt(data.encode())
        return base64.b64encode(encrypted).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt base64 encoded data and return original string"""
        if not encrypted_data:
            raise ValueError("Cannot decrypt empty data")
        
        try:
            decoded = base64.b64decode(encrypted_data.encode())
            decrypted = self.fernet.decrypt(decoded)
            return decrypted.decode()
        except Exception as e:
            raise ValueError(f"Decryption failed: {str(e)}")
    
    @staticmethod
    def generate_key() -> str:
        """Generate a new Fernet encryption key"""
        return Fernet.generate_key().decode()

# Global encryption service instance will be initialized with settings
encryption_service: Optional[EncryptionService] = None

def get_encryption_service() -> EncryptionService:
    """Get or create encryption service instance"""
    global encryption_service
    if encryption_service is None:
        from ..config import settings
        encryption_service = EncryptionService(settings.ENCRYPTION_KEY)
    return encryption_service