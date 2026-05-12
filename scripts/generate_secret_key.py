import secrets

def generate_secret_key():
    key = secrets.token_hex(32)
    print("\nSuccessfully generated a new random SECRET_KEY:\n")
    print(key)
    print("\nCopy this key and paste it into your .env file as:")
    print(f"SECRET_KEY={key}\n")

if __name__ == "__main__":
    generate_secret_key()
