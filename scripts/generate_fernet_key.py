import base64
import os

try:
    from cryptography.fernet import Fernet
except ImportError:
    print("Please install cryptography first: pip install cryptography")
    exit(1)

def generate_key():
    key = Fernet.generate_key()
    print("\nSuccessfully generated a new Fernet ENCRYPTION_KEY:\n")
    print(key.decode("utf-8"))
    print("\nCopy this key and paste it into your .env file as:")
    print(f"ENCRYPTION_KEY={key.decode('utf-8')}\n")

if __name__ == "__main__":
    generate_key()
