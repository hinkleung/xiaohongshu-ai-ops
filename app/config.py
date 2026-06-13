import os
import logging
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

XHS_MCP_URL = os.getenv("XHS_MCP_URL", "http://localhost:18060")
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/app.db")
UPLOADS_DIR = os.getenv("UPLOADS_DIR", "data/uploads")
FERNET_KEY_FILE = os.path.join(os.path.dirname(DATABASE_PATH) or ".", ".fernet_key")


def _load_fernet() -> Fernet:
    key = os.getenv("FERNET_KEY")
    if key:
        return Fernet(key.encode())

    # Try persisted key file
    if os.path.exists(FERNET_KEY_FILE):
        with open(FERNET_KEY_FILE, "rb") as f:
            return Fernet(f.read())

    # Generate and persist
    key = Fernet.generate_key()
    os.makedirs(os.path.dirname(FERNET_KEY_FILE) or ".", exist_ok=True)
    with open(FERNET_KEY_FILE, "wb") as f:
        f.write(key)
    logger.warning("Generated new FERNET_KEY and saved to %s", FERNET_KEY_FILE)
    return Fernet(key)


fernet = _load_fernet()


def encrypt_api_key(key: str) -> str:
    return fernet.encrypt(key.encode()).decode()


def decrypt_api_key(encrypted: str) -> str:
    return fernet.decrypt(encrypted.encode()).decode()
