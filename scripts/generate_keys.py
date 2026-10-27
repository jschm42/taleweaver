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
import os
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


def generate_hex_value() -> str:
    """Generate a cryptographically secure 32-byte hex string."""
    return os.urandom(32).hex()


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
        dest="only_hex",
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
        fernet_val = generate_fernet_key()
        if args.raw:
            sys.stdout.write(f"{fernet_val}\n")
        else:
            sys.stdout.write(f"ENCRYPTION_KEY={fernet_val}\n")
        return

    if args.only_hex:
        hex_val = generate_hex_value()
        if args.raw:
            sys.stdout.write(f"{hex_val}\n")
        else:
            sys.stdout.write(f"SECRET_KEY={hex_val}\n")
        return

    # Default: generate both
    fernet_val = generate_fernet_key()
    hex_val = generate_hex_value()

    if args.raw:
        sys.stdout.write(f"Fernet: {fernet_val}\n")
        sys.stdout.write(f"Secret: {hex_val}\n")
    else:
        sys.stdout.write("# Generated TaleWeaver security keys:\n")
        sys.stdout.write(f"ENCRYPTION_KEY={fernet_val}\n")
        sys.stdout.write(f"SECRET_KEY={hex_val}\n")


if __name__ == "__main__":
    main()
