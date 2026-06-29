#!/usr/bin/env python3
"""Re-apply UTF-8 encoding fix to Hermes cron scheduler after updates.

Root cause: cron/scheduler.py uses subprocess.run(text=True) without
explicit encoding, causing Windows to decode Chinese script output with
cp936/GBK instead of UTF-8 → 乱码 in Telegram deliveries.

This patch adds encoding="utf-8", errors="replace" to the subprocess.run
call in _execute_script() so Chinese output is read correctly.

Run this after every `hermes update` that overwrites site-packages.
"""
import sys, os, re

def find_scheduler():
    """Locate the installed cron/scheduler.py."""
    try:
        import cron
        return os.path.join(os.path.dirname(cron.__file__), "scheduler.py")
    except ImportError:
        pass
    # Fallback: search common paths
    base = os.path.expanduser("~/.hermes-web-ui/desktop-runtime")
    if os.path.isdir(base):
        for root, dirs, files in os.walk(base):
            if "scheduler.py" in files and "cron" in root:
                return os.path.join(root, "scheduler.py")
    return None

def apply_patch(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    if 'encoding="utf-8"' in content and 'subprocess.run' in content:
        # Check if the specific pattern already has the fix
        if 'text=True,\n            encoding="utf-8"' in content or 'text=True,\n                encoding="utf-8"' in content:
            print("Patch already applied — no changes needed.")
            return True
    
    # Find the pattern: text=True, followed by timeout=
    pattern = r'(text=True,\s*\n)(\s+timeout=script_timeout)'
    replacement = r'\1            encoding="utf-8",\n            errors="replace",\n\2'
    
    new_content, count = re.subn(pattern, replacement, content)
    if count == 0:
        print("WARNING: Pattern not found — Hermes may have changed the code.")
        print("Manual inspection needed. Look for subprocess.run(text=True, ...)")
        return False
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)
    
    print(f"Patch applied successfully to: {filepath}")
    print(f"  Added encoding=\"utf-8\", errors=\"replace\" to subprocess.run()")
    print(f"  Restart gateway to take effect: hermes gateway restart")
    return True

if __name__ == "__main__":
    scheduler_path = find_scheduler()
    if not scheduler_path:
        print("ERROR: Could not find cron/scheduler.py")
        sys.exit(1)
    
    print(f"Target: {scheduler_path}")
    apply_patch(scheduler_path)