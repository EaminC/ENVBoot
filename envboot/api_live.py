import json
import os
import requests

def load_cached_or_live(api_url: str, cache_path: str):
    """Fetches data from Chameleon API or local cache."""
    if os.path.exists(cache_path):
        with open(cache_path) as f:
            return json.load(f)
    print(f"[fetch] {api_url}")
    resp = requests.get(api_url)
    resp.raise_for_status()
    data = resp.json()
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, "w") as f:
        json.dump(data, f, indent=2)
    return data


def extract_zone_capacities(sites_json, uc_nodes_json):
    """Returns dict like {'uc:chameleon': 132, 'uc:chameleon_gpu': 20}."""
    capacities = {}

    # Example: just count UC nodes
    nodes = uc_nodes_json["items"]
    total_nodes = len(nodes)
    gpu_nodes = sum(1 for n in nodes if n.get("gpu", {}).get("gpu", False))

    capacities["uc:chameleon"] = total_nodes
    capacities["uc:chameleon_gpu"] = gpu_nodes

    # Optional: extract other zones from /sites
    for site in sites_json.get("items", []):
        capacities[site["uid"]] = 0  # placeholder for now

    return capacities


def get_real_zone_capacities():
    """Wrapper that fetches and summarizes Chameleon resources."""
    sites = load_cached_or_live(
        "https://api.chameleoncloud.org/sites",
        "examples/api_samples/sites.json"
    )
    uc_nodes = load_cached_or_live(
        "https://api.chameleoncloud.org/sites/uc/clusters/chameleon/nodes",
        "examples/api_samples/uc_chameleon_nodes.json"
    )
    return extract_zone_capacities(sites, uc_nodes)
