import os

from cryptography.fernet import Fernet


def _fernet() -> Fernet:
    secret = os.environ.get("APP_SECRET")
    if not secret:
        raise RuntimeError(
            "APP_SECRET not set. Generate one with: "
            "python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
        )
    return Fernet(secret.encode())


def encrypt(plaintext: str) -> bytes:
    return _fernet().encrypt(plaintext.encode())


def decrypt(ciphertext: bytes) -> str:
    return _fernet().decrypt(ciphertext).decode()
