#!/usr/bin/env python3
"""
TaleWeaver Cryptographic Key Generator

Generates ENCRYPTION_KEY (Fernet base64) and SECRET_KEY (32-byte hex)
for TaleWeaver configuration and development.

Usage:
  python scripts/generate_keys.py          # Generate both keys
  python scripts/generate_keys.py --fernet # Generate Fernet key only
  python scripts/generate_keys.py --secret # Generate Secret key only
  python scripts/generate_keys.py --raw    # Output raw values only
"""

import argparse
import secrets
import sys


def generate_fernet_key() -> str:
    try:
        from cryptography.fernet import Fernet
        return Fernet.generate_key().decode("utf-8")
    except ImportError:
        print(
            "ERROR: 'cryptography' package is required to generate Fernet keys.\n"
            "Run: poetry install",
            file=sys.stderr,
        )
        sys.exit(1)


def generate_secret_key() -> str:
    return secrets.token_hex(32)


def main():
    parser = argparse.ArgumentParser(
        description="Generate cryptographic keys for TaleWeaver (.env)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--fernet",
        action="store_true",
        help="Generate only the Fernet ENCRYPTION_KEY",
    )
    group.add_argument(
        "--secret",
        action="store_true",
        help="Generate only the SECRET_KEY (32-byte hex)",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Print raw key value without .env variable formatting",
    )

    args = parser.parse_args()

    if args.fernet:
        key = generate_fernet_key()
        if args.raw:
            print(key)
        else:
            print(f"ENCRYPTION_KEY={key}")
        return

    if args.secret:
        key = generate_secret_key()
        if args.raw:
            print(key)
        else:
            print(f"SECRET_KEY={key}")
        return

    # Default: generate both
    fernet_key = generate_fernet_key()
    secret_key = generate_secret_key()

    if args.raw:
        print(f"Fernet: {fernet_key}")
        print(f"Secret: {secret_key}")
    else:
        print("# Generated TaleWeaver security keys:")
        print(f"ENCRYPTION_KEY={fernet_key}")
        print(f"SECRET_KEY={secret_key}")


if __name__ == "__main__":
    main()
