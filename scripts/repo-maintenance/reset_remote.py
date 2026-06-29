import subprocess, json, os

# Read the token from a temp file approach - write it to a temp header file
import tempfile

TOKEN = os.environ.get("GITHUB_TOKEN", "")
OWNER = "amidaidai"
REPO = "ami-hermes"

# Step 1: Delete the repo
print("=== Step 1: Delete remote repo ===")
proc = subprocess.run(
    ["curl", "-sS", "-X", "DELETE", f"https://api.github.com/repos/{OWNER}/{REPO}",
     "-H", f"Authorization: Bearer {TOKEN}",
     "-H", "Accept: application/vnd.github.v3+json"],
    capture_output=True, text=True, timeout=30
)
print(f"Delete response: {proc.stdout}")

# Step 2: Recreate the repo
print("\n=== Step 2: Recreate repo ===")
payload = json.dumps({
    "name": REPO,
    "description": "Hermes AI assistant personalized configuration - Ami Hermes",
    "private": False,
    "auto_init": False
})
proc = subprocess.run(
    ["curl", "-sS", "-X", "POST", f"https://api.github.com/user/repos",
     "-H", f"Authorization: Bearer {TOKEN}",
     "-H", "Accept: application/vnd.github.v3+json",
     "-H", "Content-Type: application/json",
     "-d", payload],
    capture_output=True, text=True, timeout=30
)
print(f"Create response: {proc.stdout[:500]}")

if "Bad credentials" in proc.stdout or "Bad credentials" in proc.stderr:
    print("\n❌ Token invalid or lacks repo deletion permissions")
    exit(1)

# Step 3: Push local repo
print("\n=== Step 3: Force push local repo ===")
AUTH_URL = f"https://{OWNER}:{TOKEN}@github.com/{OWNER}/{REPO}.git"
proc = subprocess.run(
    ["git", "-C", f"D:/Hermes agent", "remote", "set-url", "origin", AUTH_URL],
    capture_output=True, text=True, timeout=10
)
proc = subprocess.run(
    ["git", "-C", f"D:/Hermes agent", "push", "--force", "origin", "main"],
    capture_output=True, text=True, timeout=60
)
print(f"Push stdout: {proc.stdout}")
print(f"Push stderr: {proc.stderr}")
if proc.returncode == 0:
    print("\n✅ Done! Remote repo cleared and re-pushed successfully.")
else:
    print(f"\n❌ Push failed with code {proc.returncode}")
