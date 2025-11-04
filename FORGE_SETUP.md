## Forge API (OpenAI-compatible) setup

This guide ensures your scripts that use `from openai import OpenAI` with `base_url="https://api.forge.tensorblock.co/v1"` run smoothly, auto-load `.env`, and verify the API connection.

### 1) Install dependencies

```bash
pip install -r requirements.txt
```

This includes:
- openai (Python SDK v1.x)
- python-dotenv (auto-load .env)
- pandas (if your scripts rely on it)

If you’re using an editable install of this package:

```bash
pip install -e .
```

### 2) Configure your API key

Create a `.env` file in the project root (same directory as this README) with your Forge API key:

```
# Required for Forge (OpenAI-compatible)
FORGE_API_KEY=sk-...your_forge_api_key...

# Optional alias if you already use OpenAI SDK patterns
# OPENAI_API_KEY=sk-...your_forge_api_key...
```

Notes:
- The repository auto-loads `.env` via `python-dotenv` (see `envboot/llm_client.py` and the connectivity script below).
- You can also export the variable in your shell instead of `.env`.

### 3) Verify connectivity (quick check)

Run the included script to confirm your key and base URL work:

```bash
python scripts/forge_check.py
```

Expected output on success:

```
Forge check: OK ✅
- Models: <model-1>, <model-2>, ...
```

If it fails, you’ll see helpful diagnostics (missing key, auth error, network/proxy issues).

### 4) Using the client in your code

Example pattern (v1 SDK):

```python
from dotenv import load_dotenv
from openai import OpenAI
import os

load_dotenv()  # auto-load .env in project root
client = OpenAI(
    base_url="https://api.forge.tensorblock.co/v1",
    api_key=os.environ.get("FORGE_API_KEY") or os.environ["OPENAI_API_KEY"],
)

# simple smoke call
models = client.models.list()
print([m.id for m in models.data][:5])
```

For chat completion (if supported by your Forge deployment):

```python
resp = client.chat.completions.create(
    model="OpenAI/gpt-4.1",   # replace with an available model from models.list()
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Say hello in one sentence."}
    ],
    temperature=0,
)
print(resp.choices[0].message.content)
```

### Troubleshooting

- Missing key: Set `FORGE_API_KEY` (or `OPENAI_API_KEY`) in `.env` or your shell.
- 401/403 errors: Confirm your key is valid and has access to the Forge deployment.
- Connection errors: Check proxies/VPN/firewalls. Ensure the base URL is exactly `https://api.forge.tensorblock.co/v1`.
- Model errors: Call `client.models.list()` to discover available `model` identifiers for your deployment.

### What’s already wired here

- `envboot/llm_client.py` auto-loads `.env` and builds an `OpenAI` client pointing at Forge with `FORGE_API_KEY`.
- `scripts/forge_check.py` validates connectivity and lists models.
