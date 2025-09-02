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
from envboot.prompt import build_prompt, prompt_downgrade_advisor, prompt_complexity_review
from envboot.llm_client import run_prompt, must_json_dict, validate_request_obj
from envboot.analysis import analyze_repo_complexity_with_signals, map_complexity_to_request
from envboot.ai_hooks import ai_complexity_review, ai_downgrade_advisor
from envboot.models import ComplexityTier   


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

    # # Hardware rough requirements from README
    # p1 = build_prompt("hardware", readme_text=readme)
    # out1 = run_prompt(p1)
    # print("Hardware JSON:\n", out1, "\n")

    # # Agent decision over mock API/JSON
    # p2 = build_prompt("mock_api", resource_json=resource_json)
    # out2 = run_prompt(p2)
    # print("Mock API decision JSON:\n", out2, "\n")

    # # Analyzer infers minimums from messy report
    # p3 = build_prompt("analysis", report_text=report)
    # out3 = run_prompt(p3)
    # print("Analyzer JSON:\n", out3, "\n")



    # --- Test AI Downgrade Advisor ---
    original_req = {"vcpus": 16, "ram_gb": 64, "gpus": 1, "disk_gb": 80, "bare_metal": True}
    policy = {
    "max_vcpu_reduction_ratio": 0.5,
    "max_ram_reduction_ratio": 0.2,
    "max_duration_increase_ratio": 2.0,
    "allow_gpu_to_cpu": False,
    "require_pass_smoketest": False
    }
    tier = "HEAVY"

    p_dg = prompt_downgrade_advisor(json.dumps(original_req), json.dumps(policy), tier)
    out_dg = run_prompt(p_dg)
    dg = must_json_dict(out_dg)
    validate_request_obj(dg["downgraded_request"])
    print("AI Downgrade Suggestion:", json.dumps(dg, indent=2))


    # # --- Test AI Complexity Review ---
    signals = {"gpu_frameworks": ["torch"], "cuda_files": 0, "final_score": 5, "tier": "HEAVY"}
    mapped_request = {"vcpus": 8, "ram_gb": 32, "gpus": 1, "disk_gb": 80, "bare_metal": False}

    p_cx = prompt_complexity_review(json.dumps(signals), json.dumps(mapped_request))
    out_cx = run_prompt(p_cx)
    cx = must_json_dict(out_cx)
    print("AI Complexity Review:", json.dumps(cx, indent=2))


    # --- Test AI Complexity Review with signals ---
    # Allow overriding repo path and/or faking GPU signals via env vars for testing.
    repo = os.environ.get("ENVBOOT_REPO", ".")
    fake_gpu = os.environ.get("ENVBOOT_FAKE_GPU", "").strip().lower() in {"1", "true", "yes", "on"}

    if fake_gpu:
        tier = ComplexityTier.HEAVY
        signals = {"gpu_frameworks": ["torch"], "cuda_files": 1, "final_score": 5, "tier": "HEAVY"}
    else:
        tier, signals = analyze_repo_complexity_with_signals(repo)
    mapped = map_complexity_to_request(tier).__dict__

    final_request = ai_complexity_review(signals, mapped)
    print("Complexity final request:", final_request)

    # # Example downgrade
    original_req = mapped
    policy = {"max_vcpu_reduction_ratio": 0.5, "max_ram_reduction_ratio": 0.2, "max_duration_increase_ratio": 2.0}
    tier_name = tier.value
    downgraded = ai_downgrade_advisor(original_req, policy, tier_name)
    print("Downgraded request:", downgraded)



    # --- Test AI Complexity Review with signals ---
    # GPU-heavy repo
    signals = {"gpu_frameworks": ["torch"], "cuda_files": 0, "final_score": 5, "tier": "HEAVY"}
    mapped_request = {"vcpus": 8, "ram_gb": 32, "gpus": 1, "disk_gb": 80, "bare_metal": False}

    final_request = ai_complexity_review(signals, mapped_request)
    print("AI Complexity Review (GPU-heavy):", final_request)

    # Looser RAM cuts
    original_req = {"vcpus": 4, "ram_gb": 8, "gpus": 0, "disk_gb": 20, "bare_metal": False}
    policy = {"max_vcpu_reduction_ratio": 0.5, "max_ram_reduction_ratio": 0.4, "max_duration_increase_ratio": 2.0}

    downgraded = ai_downgrade_advisor(original_req, policy, "MODERATE")
    print("AI Downgrade Advisor (looser RAM cuts):", downgraded)


    # Lower confidence threshold
    signals = {"gpu_frameworks": [], "cuda_files": 0, "final_score": 0, "tier": "SIMPLE"}
    mapped_request = {"vcpus": 2, "ram_gb": 4, "gpus": 0, "disk_gb": 20, "bare_metal": False}

    final_request = ai_complexity_review(signals, mapped_request, confidence_threshold=0.6)
    print("AI Complexity Review (low threshold):", final_request)




