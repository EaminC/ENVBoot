#!/usr/bin/env python3
"""
Quick connectivity check for Forge's OpenAI-compatible API.

Behavior:
- Loads .env automatically (project root or parents)
- Reads FORGE_API_KEY (or OPENAI_API_KEY as a fallback)
- Calls models.list() against base_url=https://api.forge.tensorblock.co/v1
- Prints a friendly success/failure message and exits non-zero on failure
"""

import os
import sys
from typing import Optional

from dotenv import load_dotenv, find_dotenv

try:
    # OpenAI Python SDK v1.x
    from openai import OpenAI
except Exception as e:
    print("Error: 'openai' package not installed. Install dependencies with 'pip install -r requirements.txt'.")
    print(f"Details: {e}")
    sys.exit(2)


def get_api_key() -> Optional[str]:
    # Prefer FORGE_API_KEY, but allow OPENAI_API_KEY as a convenience alias
    return os.getenv("FORGE_API_KEY") or os.getenv("OPENAI_API_KEY")


def main() -> int:
    # Auto-load .env from the nearest ancestor directory
    env_path = find_dotenv(usecwd=True)
    if env_path:
        load_dotenv(env_path)

    api_key = get_api_key()
    if not api_key:
        print("Forge check: missing API key.")
        print("Set FORGE_API_KEY in your environment or .env (or use OPENAI_API_KEY).")
        return 2

    client = OpenAI(
        base_url="https://api.forge.tensorblock.co/v1",
        api_key=api_key,
    )

    # Use a safe, low-cost call to verify connectivity. Most OpenAI-compatible
    # backends implement models.list(); if not, the error will be informative.
    try:
        resp = client.models.list()
    except Exception as e:
        print("Forge check: FAILED to reach API.")
        print("- Ensure your key is valid and has access")
        print("- Check for proxies/VPN/firewall issues")
        print("- Base URL should be https://api.forge.tensorblock.co/v1")
        print(f"Details: {e}")
        return 1

    # Print a compact summary of available models
    try:
        model_ids = [m.id for m in getattr(resp, "data", [])]
    except Exception:
        model_ids = []

    print("Forge check: OK ✅")
    if model_ids:
        preview = ", ".join(model_ids[:5])
        more = "" if len(model_ids) <= 5 else f" (+{len(model_ids)-5} more)"
        print(f"- Models: {preview}{more}")
    else:
        print("- Connected, but no models listed by the API.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
