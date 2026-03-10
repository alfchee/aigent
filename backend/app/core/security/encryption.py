import os
from cryptography.fernet import Fernet
from typing import Optional
from pathlib import Path

class EncryptionService:
    def __init__(self, key: Optional[str] = None):
        self.key = key or os.getenv("ENCRYPTION_KEY")
        if not self.key:
            # Check for local key file
            key_file = Path(".secret.key")
            if key_file.exists():
                self.key = key_file.read_text().strip()
            else:
                # Generate a key if not provided (for dev/testing)
                self.key = Fernet.generate_key().decode()
                key_file.write_text(self.key)
                print(f"WARNING: ENCRYPTION_KEY not found. Generated temporary key in {key_file}")
        
        try:
            self.cipher_suite = Fernet(self.key.encode() if isinstance(self.key, str) else self.key)
        except Exception as e:
            raise ValueError(f"Invalid encryption key: {e}")

    def encrypt(self, plain_text: str) -> str:
        if not plain_text:
            return ""
        return self.cipher_suite.encrypt(plain_text.encode()).decode()

    def decrypt(self, cipher_text: str) -> str:
        if not cipher_text:
            return ""
        return self.cipher_suite.decrypt(cipher_text.encode()).decode()

# Global instance
_encryption_service: Optional[EncryptionService] = None

def get_encryption_service() -> EncryptionService:
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service
