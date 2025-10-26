#!/usr/bin/env python3

import json
import os
import sys
from datetime import datetime
import requests
from collections import defaultdict
from typing import Dict, List, Tuple, Any, Optional

def load_json(path: str) -> dict:
    """Load JSON from a file."""
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {path}: {e}", file=sys.stderr)
        sys.exit(1)

def save_json(obj: Any, path: str) -> None:
    """Save JSON to a file with pretty formatting."""
    try:
        with open(path, 'w') as f:
            json.dump(obj, f, indent=2, sort_keys=True)
    except Exception as e:
        print(f"Error saving to {path}: {e}", file=sys.stderr)
        sys.exit(1)

def normalize_iso_utc(dt_str: str) -> str:
    """Convert various datetime formats to UTC ISO 8601 without fractional seconds."""
    try:
        # Handle various input formats
        for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(dt_str, fmt)
                break
            except ValueError:
                continue
        else:
            raise ValueError(f"Unrecognized datetime format: {dt_str}")
        
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception as e:
        print(f"Error normalizing datetime {dt_str}: {e}", file=sys.stderr)
        return dt_str

def index_nodes(nodes: List[dict]) -> Dict[str, dict]:
    """Create indices for nodes by resource_id, uuid, and hostname."""
    indices = {
        'by_resource_id': {},
        'by_uuid': {},
        'by_hostname': {}
    }
    
    for node in nodes:
        # Resource ID hint index
        if 'resource_id_hint' in node:
            indices['by_resource_id'][str(node['resource_id_hint'])] = node
            
        # UUID index (node_uuid in our case is uid)
        if 'uid' in node:
            indices['by_uuid'][node['uid']] = node
            
        # Hostname index (hostname in our case is node_name)
        if 'node_name' in node:
            indices['by_hostname'][node['node_name']] = node
    
    return indices

def get_allocations() -> Tuple[List[dict], str]:
    """Get allocations from file or API."""
    alloc_path = os.getenv('ALLOCATIONS_PATH', './allocations.json')
    
    # Check file first
    if os.path.exists(alloc_path):
        return load_json(alloc_path), 'allocations_file'
    
    # Try API if env vars exist
    blazar_url = os.getenv('BLAZAR_BASE_URL')
    token = os.getenv('OS_TOKEN')
    
    if blazar_url and token:
        try:
            headers = {'X-Auth-Token': token}
            resp = requests.get(f"{blazar_url}/v1/allocations", headers=headers)
            resp.raise_for_status()
            return resp.json(), 'allocations_api'
        except Exception as e:
            print(f"Error fetching allocations from API: {e}", file=sys.stderr)
            sys.exit(1)
    
    print("No allocations source available - need either ALLOCATIONS_PATH or BLAZAR_BASE_URL+OS_TOKEN", 
          file=sys.stderr)
    sys.exit(1)

def join_allocations_to_nodes(allocations: List[dict], node_index: Dict[str, dict]) -> Tuple[dict, list, dict]:
    """Join allocations to nodes and track statistics."""
    mapped_nodes = defaultdict(lambda: {'reservations': []})
    unmatched = []
    stats = {
        'total_nodes': len(set().union(*[set(idx.keys()) for idx in node_index.values()])),
        'nodes_with_allocations': 0,
        'total_allocations': len(allocations)
    }
    
    for alloc in allocations:
        resource_id = str(alloc.get('resource_id', ''))
        node = None
        
        # Try matching by resource_id, uuid, then hostname
        if resource_id in node_index['by_resource_id']:
            node = node_index['by_resource_id'][resource_id]
        elif resource_id in node_index['by_uuid']:
            node = node_index['by_uuid'][resource_id]
        elif resource_id in node_index['by_hostname']:
            node = node_index['by_hostname'][resource_id]
        
        if node:
            node_key = node['uid']
            if not mapped_nodes[node_key].get('node_data'):
                mapped_nodes[node_key]['node_data'] = {
                    'node_uuid': node['uid'],
                    'hostname': node['node_name'],
                    'resource_id': resource_id,
                    'cluster_id': node.get('cluster', 'unknown')  # Adding cluster_id for grouping
                }
            
            # Normalize reservation data
            reservation = {
                'reservation_id': alloc.get('reservation_id', ''),
                'lease_id': alloc.get('lease_id', ''),
                'start': normalize_iso_utc(alloc.get('start_date', '')),
                'end': normalize_iso_utc(alloc.get('end_date', ''))
            }
            
            # Add optional user_name if present in extras
            if 'extras' in alloc and 'user_name' in alloc['extras']:
                reservation['user_name'] = alloc['extras']['user_name']
            
            mapped_nodes[node_key]['reservations'].append(reservation)
        else:
            unmatched.append({
                'resource_id': resource_id,
                'reservations': [{
                    'reservation_id': alloc.get('reservation_id', ''),
                    'lease_id': alloc.get('lease_id', ''),
                    'start': normalize_iso_utc(alloc.get('start_date', '')),
                    'end': normalize_iso_utc(alloc.get('end_date', ''))
                }]
            })
    
    # Sort reservations by start time
    for node in mapped_nodes.values():
        node['reservations'].sort(key=lambda x: x['start'])
    
    stats['nodes_with_allocations'] = len([n for n in mapped_nodes.values() if n['reservations']])
    
    return dict(mapped_nodes), unmatched, stats

def group_by_site_and_cluster(mapped_nodes: dict, clusters: dict, sites: dict) -> List[dict]:
    """Group nodes by site and cluster."""
    site_summaries = []
    
    # Create cluster lookup from items array
    cluster_lookup = {c['uid']: c for c in clusters.get('items', [])}
    
    # Create site lookup with zones mapping
    site_lookup = {}
    for site in sites.get('items', []):
        site_lookup[site['uid']] = {
            'site_id': site['uid'],
            'display_name': site['name'],
            'clusters': defaultdict(lambda: {
                'nodes': [],
                'name': 'unknown'
            })
        }
    
    # First pass: assign nodes to clusters within sites
    for node_id, node_data in mapped_nodes.items():
        if 'node_data' not in node_data:
            continue
            
        cluster_id = node_data['node_data'].get('cluster_id', 'unknown')
        node_entry = {
            'node_uuid': node_data['node_data']['node_uuid'],
            'hostname': node_data['node_data']['hostname'],
            'resource_id': node_data['node_data']['resource_id'],
            'reservations': node_data['reservations']
        }
        
        # Try to find the right site for this cluster
        site_found = False
        for site_id, site in site_lookup.items():
            if any(cluster_id in cluster.get('clusters', []) for cluster in sites['items'] if cluster['uid'] == site_id):
                site['clusters'][cluster_id]['nodes'].append(node_entry)
                site['clusters'][cluster_id]['name'] = cluster_lookup.get(cluster_id, {}).get('name', cluster_id)
                site_found = True
                break
        
        # If no site found, add to unknown site
        if not site_found:
            if 'unknown' not in site_lookup:
                site_lookup['unknown'] = {
                    'site_id': 'unknown',
                    'display_name': 'Unknown Site',
                    'clusters': defaultdict(lambda: {
                        'nodes': [],
                        'name': 'unknown'
                    })
                }
            site_lookup['unknown']['clusters'][cluster_id]['nodes'].append(node_entry)
            site_lookup['unknown']['clusters'][cluster_id]['name'] = cluster_lookup.get(cluster_id, {}).get('name', cluster_id)
    
    # Convert the nested structure to the final format
    for site_id, site in site_lookup.items():
        if not site['clusters']:
            continue
            
        site_entry = {
            'site_id': site['site_id'],
            'display_name': site['display_name'],
            'clusters': []
        }
        
        # Convert clusters dict to list and sort nodes
        for cluster_id, cluster_data in site['clusters'].items():
            cluster_entry = {
                'cluster_id': cluster_id,
                'name': cluster_data['name'],
                'nodes': sorted(cluster_data['nodes'], key=lambda x: x['hostname'])
            }
            site_entry['clusters'].append(cluster_entry)
        
        # Sort clusters
        site_entry['clusters'].sort(key=lambda x: x['cluster_id'])
        site_summaries.append(site_entry)
    
    # Sort sites
    return sorted(site_summaries, key=lambda x: x['site_id'])

def main():
    """Main entry point for the script."""
    # Load static data
    nodes = load_json(os.getenv('NODES_PATH', './uc_chameleon_nodes.json'))
    clusters = load_json(os.getenv('CLUSTERS_PATH', './uc_clusters.json'))
    sites = load_json(os.getenv('SITES_PATH', './sites.json'))
    
    # Get node indices
    node_index = index_nodes(nodes.get('items', []))
    
    # Get allocations
    allocations, source = get_allocations()
    
    # Join allocations with nodes
    mapped_nodes, unmatched, stats = join_allocations_to_nodes(allocations, node_index)
    
    # Group by site and cluster
    site_summaries = group_by_site_and_cluster(mapped_nodes, clusters, sites)
    
    # Build final result
    result = {
        'fetched_at': datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        'source': source,
        'site_summaries': site_summaries,
        'unmatched_allocations': unmatched,
        'stats': stats
    }
    
    # Save results
    output_path = os.getenv('OUTPUT_PATH', './lease_results_live.json')
    save_json(result, output_path)
    
    # Print summary
    print(f"Processed {stats['total_allocations']} allocations across {stats['total_nodes']} nodes "
          f"({stats['nodes_with_allocations']} with allocations). "
          f"Results written to {output_path}")

if __name__ == "__main__":
    main()