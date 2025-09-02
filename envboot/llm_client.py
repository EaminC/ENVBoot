# envboot/llm_client.py
import os, json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
FORGE_API_KEY = os.environ.get("FORGE_API_KEY")
if not FORGE_API_KEY:
    raise RuntimeError("Missing FORGE_API_KEY env var")

client = OpenAI(
    base_url="https://api.forge.tensorblock.co/v1",
    api_key=FORGE_API_KEY,
)

def run_prompt(prompt_text: str, json_only: bool = True) -> str:
    completion = client.chat.completions.create(
        model="OpenAI/gpt-4.1",
        messages=[
            {"role": "developer", "content": "You are a helpful assistant. Return concise, correct results."},
            {"role": "user", "content": prompt_text}
        ],
        temperature=0
    )
    out = completion.choices[0].message.content
    if json_only:
        _ = parse_strict_json(out)
    return out

def parse_strict_json(s: str) -> dict:
    i, j = s.find("{"), s.rfind("}")
    if i < 0 or j < 0:
        raise ValueError("Model did not return JSON")
    return json.loads(s[i:j+1])

def must_json_dict(s: str) -> dict:
    d = parse_strict_json(s)
    if not isinstance(d, dict):
        raise ValueError("Expected JSON object")
    return d

def validate_request_obj(obj: dict):
    for k in ["vcpus","ram_gb","gpus","disk_gb","bare_metal"]:
        if k not in obj:
            raise ValueError(f"Missing request field: {k}")
    if not isinstance(obj["vcpus"], int) or obj["vcpus"] < 1:
        raise ValueError("vcpus must be int >= 1")
    if not isinstance(obj["ram_gb"], int) or obj["ram_gb"] < 1:
        raise ValueError("ram_gb must be int >= 1")
    if not isinstance(obj["gpus"], int) or obj["gpus"] < 0:
        raise ValueError("gpus must be int >= 0")
    if not isinstance(obj["disk_gb"], int) or obj["disk_gb"] < 1:
        raise ValueError("disk_gb must be int >= 1")
    if not isinstance(obj["bare_metal"], bool):
        raise ValueError("bare_metal must be bool")
