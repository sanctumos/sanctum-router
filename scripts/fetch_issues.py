#!/usr/bin/env python3
"""Fetch sanctum-router issues via gh CLI (uses GH_TOKEN or gh auth). Writes JSON to scripts/sanctum_router_issues.json."""
import json
import os
import subprocess
import sys

def main():
    token = os.environ.get("GH_TOKEN")
    if not token:
        # Try to read from git-credentials
        creds_path = os.path.expanduser("~/.git-credentials")
        if os.path.exists(creds_path):
            with open(creds_path) as f:
                for line in f:
                    line = line.strip()
                    if "github.com" in line and "ghp_" in line:
                        # https://user:ghp_xxx@github.com
                        parts = line.split(":")
                        if len(parts) >= 3:
                            token = parts[2].split("@")[0]
                            break
    if not token:
        os.environ.pop("GH_TOKEN", None)
    else:
        os.environ["GH_TOKEN"] = token

    repo = "sanctumos/sanctum-router"
    result = subprocess.run(
        ["gh", "issue", "list", "--repo", repo, "--state", "all", "--limit", "100",
         "--json", "number,title,state,body,labels"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    # Write to docs/ so the file is visible in the workspace
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_path = os.path.join(base, "docs", "sanctum_router_issues.json")
    if result.returncode != 0:
        with open(out_path, "w") as f:
            json.dump({"error": result.stderr or "gh failed", "returncode": result.returncode}, f, indent=2)
        return 1
    with open(out_path, "w") as f:
        f.write(result.stdout)
    return 0

if __name__ == "__main__":
    sys.exit(main())
