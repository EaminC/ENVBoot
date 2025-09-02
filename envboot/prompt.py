# prompt = """This is the README.MD of a repo: 
# 2D Java Game Framework
# A collection of classes used for 2d game programming in Java. Much of the dirty work is taken care which makes this useful for beginner game programmers.

# Installation
# install the java JDK7.
# clone this repo.
# run make.bat if on windows, make.sh if on linux, or compile it with netbeans.
# add the .jar file created to your project.

# Usage
# After building the framework, add the .jar file to your project. Once added to your project have your class extend "game.framework.Game" and implement all the methods from the abstract class. Once everything is set up correctly just run the project and you should see a blank window with a blue background. (Better instructions to come later! :p)

# Please describe roughly the required hardware and return it in JSON format.  
# For example:
# {
#   "hardware_requirements": {
#     "cpu": "...",
#     "memory": "Please return the memory in GB, nothing else",
#     "storage": "...",
#     "gpu": "..."
#   }
# }
# """



# prompt.py

# prompts.py

HARDWARE_SCHEMA_EXAMPLE = """{
  "hardware_requirements": {
    "cpu": "e.g., 2-core x86_64",
    "memory":  "Please return the memory in GB, nothing else",
    "storage": "e.g., 1 GB free disk for jar + assets",
    "gpu":     "none or 'optional discrete GPU'"
  }
}"""

def prompt_hardware_requirements(readme_text: str) -> str:
    return f"""You are an assistant that returns ONLY JSON. 
Do not include markdown fences or extra text. The first character MUST be '{{'.

Task: Read the README text and infer rough hardware needs for running/building the project.

README:
<<<
{readme_text}
>>>

Return ONLY a JSON object with this exact schema. 
- All fields must be present. 
- "memory_gb" and "storage_gb" must be numbers only (integers). No units, no strings. 

{{
  "hardware_requirements": {{
    "cpu": "string description, e.g. 2-core x86_64",
    "memory_gb": 2,
    "storage_gb": 1,
    "gpu": "string, e.g. none or optional"
  }}
}}
"""


def prompt_mock_api(resource_json: str) -> str:
    # resource_json should already be valid JSON string
    return f"""You are an allocation agent. Return ONLY JSON. Format: output 
**one single-line, minified JSON object** (no newlines or indentation; no spaces 
after commas/colons); use double quotes for all keys/strings; JSON booleans `true/false` 
and `null`; numeric fields must be numbers. The first character MUST be '{{'.

INPUT mock API (current node + optional alternatives):
{resource_json}

Decide if we should allocate on CURRENT node or not.
Return ONLY JSON with this schema:

{{
  "choose_current_node": 0 or 1,
  "reason": "short string",
  "reservation": null or {{
    "when": "now" or "<Nh>",
    "selected_size_gb": int
  }},
  "alternatives": [
    {{
      "node_name": "string",
      "when": "now" or "<Nh>",
      "selected_size_gb": int,
      "why": "short string"
    }}
  ],
  "availability_table": [
    {{"horizon": "<Nh>", "will_end": int}}
  ]
}}
"""

def prompt_ai_analysis(report_text: str) -> str:
    return f"""You are an analyzer. Return ONLY JSON. Format: output 
**one single-line, minified JSON object** (no newlines or indentation; no spaces 
after commas/colons); use double quotes for all keys/strings; JSON booleans `true/false` 
and `null`; numeric fields must be numbers. The first character MUST be '{{'.

Analyze the text and infer minimum hardware plus a small safety headroom.

TEXT:
<<<
{report_text}
>>>

Return ONLY this JSON schema (numbers must be plain numbers; GB units implied):
{{
  "min_requirements": {{"ram_gb": int, "vcpus": int, "gpus": int, "disk_gb": int, "net_gbps": number}},
  "suggested_headroom": {{"ram_gb": int, "vcpus": int, "gpus": int, "disk_gb": int, "net_gbps": number}},
  "downgrade_policy_guess": {{"max_vcpu_reduction_ratio": number, "max_ram_reduction_ratio": number, "max_duration_increase_ratio": number}},
  "confidence": {{"overall": number, "notes": "short string"}}
}}
"""

def build_prompt(task: str, **kwargs) -> str:
    """
    task: "hardware" | "mock_api" | "analysis"
    kwargs:
      - hardware: readme_text
      - mock_api: resource_json
      - analysis: report_text
    """
    if task == "hardware":
        return prompt_hardware_requirements(kwargs["readme_text"])
    if task == "mock_api":
        return prompt_mock_api(kwargs["resource_json"])
    if task == "analysis":
        return prompt_ai_analysis(kwargs["report_text"])
    raise ValueError(f"Unknown task: {task}")



# ---------- NEW PROMPTS FOR DOWNGRADE + COMPLEXITY ----------

def prompt_downgrade_advisor(original_req_json: str, policy_json: str, tier: str) -> str:
    return f"""You are a downgrading advisor. Return ONLY JSON. Format: output 
**one single-line, minified JSON object** (no newlines or indentation; no spaces 
after commas/colons); use double quotes for all keys/strings; JSON booleans `true/false` 
and `null`; numeric fields must be numbers. First char MUST be '{{'.

Goal: propose a downgraded ResourceRequest that RESPECTS the policy caps.

INPUT:
- complexity_tier: {tier}
- original_request: {original_req_json}
- policy: {policy_json}

Rules:
- Do NOT reduce below 1 vCPU or 1 GB RAM.
- Respect policy caps exactly:
  vCPU cut ≤ max_vcpu_reduction_ratio; RAM cut ≤ max_ram_reduction_ratio.
- If complexity_tier ∈ ["HEAVY","VERY_HEAVY"] and original_request.gpus>0 and policy.allow_gpu_to_cpu is false -> keep GPUs.
- If policy.require_pass_smoketest is false, you MAY switch bare_metal -> false.
- Keep changes minimal; explain briefly.

Attention:
- After applying reduction ratios, round RAM up to the nearest integer (ceiling).
- Aim for a target that maps cleanly to available SKUs (e.g., 384/400/420/430/512). If uncertain, round up toward the next SKU.”

Return ONLY:
{{
  "downgraded_request": {{"vcpus": int, "ram_gb": int, "gpus": int, "disk_gb": int, "bare_metal": bool}},
  "respect_policy": 0 or 1,
  "expected_duration_multiplier": number,   // ≤ policy.max_duration_increase_ratio
  "why": "short string"
}}
"""

def prompt_complexity_review(signals_json: str, mapped_req_json: str) -> str:
    return f"""You are a reviewer. Return ONLY JSON. Format: output 
**one single-line, minified JSON object** (no newlines or indentation; no spaces 
after commas/colons); use double quotes for all keys/strings; JSON booleans `true/false` 
and `null`; numeric fields must be numbers. First char MUST be '{{'.

Task: Review deterministic complexity signals and the mapped request. Optionally suggest an override.

INPUT:
- signals: {signals_json}
- mapped_request: {mapped_req_json}

Guidelines:
- Override ONLY if signals clearly indicate under/over-provisioning.
- Keep numbers modest (e.g., +/- 25%) unless GPU/cuda signals are present.
- If unsure, do not override.

Attention:
- If large_codebase or test_footprint signals are present, consider bumping vCPUs or RAM even if base mapping looks OK.
- If confidence is <0.6, always return null override.

Return ONLY:
{{
  "tier_override": "SIMPLE" | "MODERATE" | "HEAVY" | "VERY_HEAVY" | null,
  "request_override": null or {{"vcpus": int, "ram_gb": int, "gpus": int, "disk_gb": int, "bare_metal": bool}},
  "why": "short string",
  "confidence": number   // 0..1
}}
"""
