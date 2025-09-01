# --- AI vs Fixed data ---
# AI-GENERATED (dynamic, derived from text):
#  - Hardware JSON (baseline requirements) from README/docs
#  - Analyzer JSON (min + headroom + policy guess) from logs/reports
#  - Decision JSON (agent's plan) from the mock API snapshot
#
# FIXED / FIXTURES (deterministic environment):
#  - capacity.machine_sizes (SKUs)
#  - forecast (simulated short-term frees)
#  - policy (if strict per experiment)
#  - now_utc, node_name
#
# HYBRID:
#  - request (either copy from Analyzer.suggested_headroom / min_requirements
#    or set manually to stress specific scenarios)


# resource_json is a FIXTURE (deterministic cluster snapshot for tests).
# Do NOT let AI generate capacity/forecast; keep them fixed for reproducibility.
# If desired, set `request` from Analyzer JSON in a separate step.


# forge.py
import os, json
from openai import OpenAI
from prompt import build_prompt
from dotenv import load_dotenv
load_dotenv()

FORGE_API_KEY = os.environ.get("FORGE_API_KEY")  # set this in your env
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
            # keep system/dev short, JSON-only logic is already in prompt_text
            {"role": "developer", "content": "You are a helpful assistant. Return concise, correct results."},
            {"role": "user", "content": prompt_text}
        ],
        temperature=0  # determinism helps schema adherence
    )
    out = completion.choices[0].message.content
    if json_only:
        _ = parse_strict_json(out)  # raises if invalid
    return out

def parse_strict_json(s: str) -> dict:
    # strip noise just in case
    i, j = s.find("{"), s.rfind("}")
    if i < 0 or j < 0:
        raise ValueError("Model did not return JSON")
    data = json.loads(s[i:j+1])
    return data

if __name__ == "__main__":
    readme = """2D Java Game Framework
A collection of classes used for 2d game programming in Java...
(install JDK7; build .jar; extend game.framework.Game; run)"""

    resource_json = json.dumps({
        "node_name": "zone-a",
        "now_utc": "2025-09-01T15:00:00Z",
        "request": {"vcpus": 4, "ram_gb": 500, "gpus": 0},
        "policy": {"max_vcpu_reduction_ratio": 0.5, "max_ram_reduction_ratio": 0.2, "max_duration_increase_ratio": 2.0},
        "capacity": {"machine_sizes": [384, 400, 420, 430, 512], "unit": "ram_gb"},
        "forecast": {"1h": 0, "2h": 2, "3h": 3}
    }, ensure_ascii=False)

    report = """Ran on 256 GB -> OOM during asset load; on 384 GB -> OK (swap 2 GB).
CPU ~6 vCPUs. No GPU needed. Disk ~1 GB plus assets (~0.5 GB). Network minimal."""

    # Hardware rough requirements from README
    p1 = build_prompt("hardware", readme_text=readme)
    out1 = run_prompt(p1)
    print("Hardware JSON:\n", out1, "\n")

    # Agent decision over mock API/JSON
    p2 = build_prompt("mock_api", resource_json=resource_json)
    out2 = run_prompt(p2)
    print("Mock API decision JSON:\n", out2, "\n")

    # Analyzer infers minimums from messy report
    p3 = build_prompt("analysis", report_text=report)
    out3 = run_prompt(p3)
    print("Analyzer JSON:\n", out3, "\n")
