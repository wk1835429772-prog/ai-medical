"""API Key 加密存储"""

import base64
import os
import socket
import getpass
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


def _derive_key() -> bytes:
    """基于本机标识派生加密密钥"""
    seed = f"{socket.gethostname()}-{getpass.getuser()}".encode()
    salt = b"clinical-assistant-v1"
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    return base64.urlsafe_b64encode(kdf.derive(seed))


def encrypt(value: str) -> str:
    """加密字符串"""
    return Fernet(_derive_key()).encrypt(value.encode()).decode()


def decrypt(encrypted: str) -> str:
    """解密字符串"""
    return Fernet(_derive_key()).decrypt(encrypted.encode()).decode()
