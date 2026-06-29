import subprocess, json, sys

# Read token from the temp file
with open(r"C:\Users\Administrator\Desktop\.gh_token.txt", "r") as f:
    TOKEN = f.read().strip()

if not TOKEN or len(TOKEN) < 30:
    print("Token invalid or too short!")
    sys.exit(1)

OWNER = "amidaidai"
REPO = "ami-hermes"

# Step 1: Delete remote repo
print("=== Step 1: Delete remote repo ===")
proc = subprocess.run(
    ["curl", "-sS", "-X", "DELETE",
     f"https://api.github.com/repos/{OWNER}/{REPO}",
     "-H", f"Authorization: token {TOKEN}",
     "-H", "Accept: application/vnd.github.v3+json",
     "-w", "\nHTTP_CODE:%{http_code}"],
    capture_output=True, text=True, timeout=30
)
stdout = proc.stdout.strip()
print(f"Result: {stdout[:300]}")

if "Bad credentials" in stdout:
    print("TOKEN IS INVALID!")
    sys.exit(1)
if "Not Found" in stdout:
    print("Repo not found on remote, will create fresh")
elif "HTTP_CODE:204" in stdout or "HTTP_CODE: 204" in stdout:
    print("Repo deleted successfully!")

# Step 2: Create repo
print("\n=== Step 2: Create repo ===")
payload = json.dumps({
    "name": REPO,
    "description": "Ami Hermes - AI personalized config",
    "private": False,
    "auto_init": False
})
proc = subprocess.run(
    ["curl", "-sS", "-X", "POST", "https://api.github.com/user/repos",
     "-H", f"Authorization: token {TOKEN}",
     "-H", "Accept: application/vnd.github.v3+json",
     "-H", "Content-Type: application/json",
     "-d", payload],
    capture_output=True, text=True, timeout=30
)
stdout = proc.stdout.strip()
resp = json.loads(stdout) if stdout else {}
if resp.get("id"):
    print(f"Repo created: {resp.get('html_url', '')}")
else:
    msg = resp.get("message", stdout[:200])
    if "already exists" in msg:
        print(f"Repo already exists: {msg}")
    else:
        print(f"Create result: {msg}")

# Step 3: Configure git and force push
print("\n=== Step 3: Force push ===")
auth_url = f"https://amidaidai:{TOKEN}@github.com/{OWNER}/{REPO}.git"
proc = subprocess.run(
    ["git", "-C", "D:/Hermes agent", "remote", "set-url", "origin", auth_url],
    capture_output=True, text=True, timeout=10
)
print(f"Remote set: {proc.stderr or 'OK'}")

proc = subprocess.run(
    ["git", "-C", "D:/Hermes agent", "push", "--force", "origin", "main"],
    capture_output=True, text=True, timeout=60
)
stdout = proc.stdout.strip()
stderr = proc.stderr.strip()
print(f"Push: {stdout or stderr}")
if proc.returncode == 0:
    print("\nSUCCESS! Remote repo cleared and re-backed up.")
else:
    print(f"\nPush failed (code {proc.returncode})")
