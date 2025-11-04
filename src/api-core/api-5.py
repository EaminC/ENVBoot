#!/usr/bin/env python3
"""
api-5.py: Provision or deploy a repository inside a reserved environment.

Callable CLI tool for EnvAgent-plus framework.
Returns structured JSON to stdout with schema: {ok, data, error, metrics, version}
Exit codes:
  0 = ok true
  1 = invalid args
  2 = backend errors (git, filesystem, timeout)
"""

import argparse
import json
import sys
import time
import os
import shutil
import subprocess
from typing import Optional

VERSION = "1.0.0"

def _clone_repo(repo: str, branch: str, workdir: str, timeout: int) -> Optional[str]:
    """Clone repo to workdir/branch. Returns path or None."""
    try:
        if os.path.exists(workdir):
            shutil.rmtree(workdir)
        os.makedirs(workdir, exist_ok=True)
        # Determine if repo is local path or URL
        if os.path.isdir(repo):
            # Local copy
            dest = os.path.join(workdir, os.path.basename(repo))
            shutil.copytree(repo, dest)
            return dest
        else:
            # Git clone
            cmd = ["git", "clone", "--branch", branch, "--single-branch", repo, workdir]
            subprocess.run(cmd, check=True, timeout=timeout)
            return workdir
    except Exception as e:
        return None

def _write_artifact(workdir: str, info: dict) -> Optional[str]:
    """Write provision.json artifact."""
    try:
        path = os.path.join(workdir, "provision.json")
        with open(path, "w") as f:
            json.dump(info, f, indent=2)
        return path
    except Exception:
        return None

def provision_env(
    reservation_id: str,
    repo: str,
    branch: str,
    workdir: str,
    dry_run: bool,
    timeout: int
) -> tuple:
    t0 = time.time()
    artifacts = []
    try:
        if not reservation_id or not repo:
            raise ValueError("reservation_id and repo are required")
        if dry_run:
            elapsed_ms = int((time.time() - t0) * 1000)
            data = {
                "reservation_id": reservation_id,
                "repo": repo,
                "branch": branch,
                "workdir": workdir,
                "status": "simulated",
                "artifacts": [os.path.join(workdir, "provision.json")],
                "dry_run": True
            }
            return {
                "ok": True,
                "data": data,
                "error": None,
                "metrics": {"elapsed_ms": elapsed_ms},
                "version": VERSION
            }, 0
        # Real mode
        repo_path = _clone_repo(repo, branch, workdir, timeout)
        if not repo_path:
            elapsed_ms = int((time.time() - t0) * 1000)
            data = {
                "reservation_id": reservation_id,
                "repo": repo,
                "branch": branch,
                "workdir": workdir,
                "status": "error",
                "artifacts": [],
                "dry_run": False
            }
            return {
                "ok": False,
                "data": data,
                "error": {"type": "CloneError", "message": "Failed to clone or copy repo."},
                "metrics": {"elapsed_ms": elapsed_ms},
                "version": VERSION
            }, 2
        # Write artifact
        info = {
            "reservation_id": reservation_id,
            "repo": repo,
            "branch": branch,
            "workdir": workdir,
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        }
        artifact_path = _write_artifact(workdir, info)
        if artifact_path:
            artifacts.append(artifact_path)
        elapsed_ms = int((time.time() - t0) * 1000)
        data = {
            "reservation_id": reservation_id,
            "repo": repo,
            "branch": branch,
            "workdir": workdir,
            "status": "prepared",
            "artifacts": artifacts,
            "dry_run": False
        }
        return {
            "ok": True,
            "data": data,
            "error": None,
            "metrics": {"elapsed_ms": elapsed_ms},
            "version": VERSION
        }, 0
    except Exception as e:
        elapsed_ms = int((time.time() - t0) * 1000)
        return {
            "ok": False,
            "data": None,
            "error": {"type": type(e).__name__, "message": str(e)},
            "metrics": {"elapsed_ms": elapsed_ms},
            "version": VERSION
        }, 1

def main():
    parser = argparse.ArgumentParser(
        description="API-5: Provision or deploy a repository inside a reserved environment",
        add_help=False
    )
    parser.add_argument("--reservation-id", required=True, help="Reservation/lease ID")
    parser.add_argument("--repo", required=True, help="Local path or Git URL")
    parser.add_argument("--branch", default="main", help="Branch to checkout (default: main)")
    parser.add_argument("--workdir", default="/tmp/envagent", help="Workspace directory (default: /tmp/envagent)")
    parser.add_argument("--timeout", type=int, default=600, help="Timeout seconds (default: 600)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate provisioning")

    args = parser.parse_args()

    result, exit_code = provision_env(
        reservation_id=args.reservation_id,
        repo=args.repo,
        branch=args.branch,
        workdir=args.workdir,
        dry_run=args.dry_run,
        timeout=args.timeout
    )

    print(json.dumps(result, indent=2))
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
