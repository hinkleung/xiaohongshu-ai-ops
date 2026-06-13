import os
from cryptography.fernet import Fernet


XHS_MCP_URL = os.getenv("XHS_MCP_URL", "http://localhost:18060")
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/app.db")
UPLOADS_DIR = os.getenv("UPLOADS_DIR", "data/uploads")

_fernet_key = os.getenv("FERNET_KEY")
if _fernet_key:
    fernet = Fernet(_fernet_key.encode())
else:
    _key = Fernet.generate_key()
    fernet = Fernet(_key)
    print(f"[WARNING] FERNET_KEY not set. Generated: {_key.decode()}")


def encrypt_api_key(key: str) -> str:
    return fernet.encrypt(key.encode()).decode()


def decrypt_api_key(encrypted: str) -> str:
    return fernet.decrypt(encrypted.encode()).decode()
