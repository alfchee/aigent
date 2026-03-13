import os
from cryptography.fernet import Fernet
from typing import Optional
from pathlib import Path

class EncryptionService:
    @staticmethod
    def _is_dev_or_test() -> bool:
        env = (
            os.getenv("NAVIBOT_ENV")
            or os.getenv("APP_ENV")
            or os.getenv("ENVIRONMENT")
            or ""
        ).strip().lower()
        return env in {"dev", "development", "local", "test", "testing"}

    @staticmethod
    def _key_file_path() -> Path:
        key_file = os.getenv("ENCRYPTION_KEY_FILE")
        if key_file:
            return Path(key_file).expanduser().resolve()
        return Path.home().joinpath(".navibot", "secret.key").resolve()

    def __init__(self, key: Optional[str] = None):
        self.key = key or os.getenv("ENCRYPTION_KEY")
        if not self.key:
            key_file = self._key_file_path()
            if key_file.exists():
                self.key = key_file.read_text(encoding="utf-8").strip()
            else:
                if not self._is_dev_or_test():
                    raise ValueError("ENCRYPTION_KEY is required outside dev/test environments")
                self.key = Fernet.generate_key().decode("utf-8")
                key_file.parent.mkdir(parents=True, exist_ok=True)
                key_file.write_text(self.key, encoding="utf-8")
                os.chmod(key_file, 0o600)
        
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
