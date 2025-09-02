# ai_hooks.py
import json
from typing import Dict, Any
from .prompt import prompt_complexity_review, prompt_downgrade_advisor
from .llm_client import run_prompt, must_json_dict, validate_request_obj

def ai_complexity_review(signals: Dict[str, Any], mapped_request: Dict[str, Any], confidence_threshold: float = 0.7) -> Dict[str, Any]:
    """Ask AI to confirm/override the mapped request. Returns the final request dict."""
    p = prompt_complexity_review(json.dumps(signals), json.dumps(mapped_request))
    out = run_prompt(p)
    res = must_json_dict(out)

    override = res.get("request_override")
    conf = float(res.get("confidence", 0))
    if override and conf >= confidence_threshold:
        validate_request_obj(override)
        return override
    return mapped_request

def ai_downgrade_advisor(original_req: Dict[str, Any], policy: Dict[str, Any], tier: str) -> Dict[str, Any]:
    """Ask AI for a policy-respecting downgraded request. Returns the downgraded request dict."""
    p = prompt_downgrade_advisor(json.dumps(original_req), json.dumps(policy), tier)
    out = run_prompt(p)
    res = must_json_dict(out)
    dr = res["downgraded_request"]
    validate_request_obj(dr)
    return dr
