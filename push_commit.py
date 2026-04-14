#!/usr/bin/env python3
"""Push a commit to GitHub using the Git Data API."""
import json, subprocess, sys, os, urllib.request, urllib.parse

akeyless_script = os.path.expanduser("~/.openclaw/workspace/dev/skills/akeyless-secrets/scripts/akeyless.py")
if not os.path.exists(akeyless_script):
    akeyless_script = subprocess.check_output("find ~ -name 'akeyless.py' -path '*/akeyless-secrets/*' 2>/dev/null | head -1", shell=True).decode().strip()

result = json.loads(subprocess.check_output(f"python3 {akeyless_script} get /credentials/api/github-pat", shell=True))
GH_TOKEN = result["value"]

OWNER = "Fiambre"
REPO = "n8n-nodes-azure-devops"
BASE = f"https://api.github.com/repos/{OWNER}/{REPO}"
HEADERS = {
    "Authorization": f"token {GH_TOKEN}",
    "Accept": "application/vnd.github+json",
    "Content-Type": "application/json",
}

def gh(method, path, data=None, params=None):
    url = f"{BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=HEADERS, method=method)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

repo_dir = os.path.dirname(os.path.abspath(__file__))

# Stage and commit locally first to get the diff
subprocess.check_call("git add -A", shell=True, cwd=repo_dir)
subprocess.check_call('git -c user.email="fiambre@users.noreply.github.com" -c user.name="Fiambre" commit -m "docs: add fork credits and upstream link in README"', shell=True, cwd=repo_dir, stderr=subprocess.DEVNULL)

parent = gh("GET", "/git/ref/heads/master")
parent_sha = parent["object"]["sha"]
print(f"Parent: {parent_sha}")

changed = subprocess.check_output("git diff-tree --no-commit-id --name-status -r HEAD", shell=True, cwd=repo_dir).decode().strip()
print(f"Changes:\n{changed}")

tree_entries = []
for line in changed.strip().split("\n"):
    if not line.strip():
        continue
    parts = line.split("\t", 1)
    status = parts[0].strip()
    filepath = parts[1].strip()

    if status == "D":
        tree_entries.append({"path": filepath, "mode": "100644", "type": "commit", "sha": None})
        continue

    full_path = os.path.join(repo_dir, filepath)
    with open(full_path, "rb") as f:
        content = f.read()

    print(f"Creating blob: {filepath} ({len(content)} bytes)")
    blob = gh("POST", "/git/blobs", data={"content": content.decode("utf-8"), "encoding": "utf-8"})
    tree_entries.append({"path": filepath, "mode": "100644", "type": "blob", "sha": blob["sha"]})

print(f"\nCreating tree with {len(tree_entries)} entries...")
tree = gh("POST", "/git/trees", data={"base_tree": parent_sha, "tree": tree_entries})
print(f"Tree: {tree['sha']}")

commit = gh("POST", "/git/commits", data={
    "message": "docs: add fork credits and upstream link in README",
    "tree": tree["sha"],
    "parents": [parent_sha],
})
print(f"Commit: {commit['sha']}")

gh("PATCH", "/git/refs/heads/master", data={"sha": commit["sha"]})
print("Ref updated! Push complete.")
