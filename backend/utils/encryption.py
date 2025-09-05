from cryptography.fernet import Fernet

class EncryptionService:
    """Service for encrypting/decrypting sensitive data"""
    
    def __init__(self, key=None):
        if key:
            self.fernet = Fernet(key)
        else:
            self.fernet = Fernet(Fernet.generate_key())
    
    def encrypt(self, data: str) -> str:
        """Encrypt a string"""
        return self.fernet.encrypt(data.encode()).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt a string"""
        return self.fernet.decrypt(encrypted_data.encode()).decode()

encryption_service = EncryptionService()
