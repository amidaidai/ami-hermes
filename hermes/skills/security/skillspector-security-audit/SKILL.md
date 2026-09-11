---
name: skillspector-security-audit
description: Use NVIDIA SkillSpector to scan Hermes community skills for vulnerabilities, classify true vs false positives, and fix real security issues.
trigger: When the user asks to audit, scan, review, or check security of installed skills, shares a SkillSpector link, or wants to vet community skills.
---

# SkillSpector Security Audit for Hermes Skills

A systematic workflow to scan all community skills with NVIDIA's SkillSpector, classify findings into true issues vs false positives, and fix what matters.

## Prerequisites

- **Python 3.12+** (SkillSpector requires it)
- **uv** or **pip** for installation
- **Docker** optional (alternative to pip install)

## Step 1: Install SkillSpector

```bash
# Clone the repo
cd /tmp
git clone https://github.com/NVIDIA/SkillSpector.git

# Create venv with Python 3.12+
uv venv --python 3.12 skillspector-venv
# On Windows (git-bash):
source skillspector-venv/Scripts/activate
# On Linux/Mac:
source skillspector-venv/bin/activate

# Install
uv pip install ./SkillSpector
```

## Step 2: Scan Community Skills

### Full scan (all skills, JSON output)
```bash
skillspector scan ~/AppData/Local/hermes/skills/community/ --no-llm --format json -o /tmp/community_scan.json
```

### Fast per-skill summary
```bash
for d in ~/AppData/Local/hermes/skills/community/*/; do
  name=$(basename "$d")
  result=$(skillspector scan "$d" --no-llm 2>&1 | grep -E "^ Score")
  echo "$name: $result"
done
```

## Step 3: Classify Findings

For a concrete audited example, see `references/hermes-community-skill-audit-2026-06-28.md`.

1910+ issues may be found on a large community tree. The vast majority are often **false positives**:

### Known False Positive Categories

| Category | Why it's FP | Action |
|----------|-------------|--------|
| Context Window Stuffing | Binary font files (.ttf, .otf) scanned as text | Skip |
| Hidden Instructions | XML comments in .xsd, .csproj, .md files | Skip |
| Tool Parameter Abuse in .ttf/.xsd/.pdf | Binary data or schema enum values | Skip |
| Chaining Abuse with "sudo" | Email addresses (e.g. sudolewis@gmail.com) | Skip |
| Credential Access for "keychain" | Image prompt descriptions (resin keychain) | Skip |
| Env Variable Harvesting `os.environ.copy()` | Standard Python for subprocess env | Skip |
| Unvalidated Output Injection `capture_output=True` | Standard safe subprocess pattern | Skip |
| Direct Prompt Extraction in SKILL.md | Skills intentionally describe their prompts | Skip |
| YARA in security-focused skills | slowmist-agent-security mentions social-engineering | Skip |
| Scope Creep in LICENSE files | License files are metadata, not scope | Skip |

### Real Issue Categories to Fix

| Category | What to check | Fix |
|----------|--------------|-----|
| **shell=True** in subprocess | Popen(cmd, shell=True) | Convert to shell=False + shlex.split() |
| **Known Vulnerable Dependencies** | CVE matches on OSV.dev | Pin to patched versions (>=) |
| **Unpinned Dependencies** | No version constraint | Add ^ or >= version |
| **Hardcoded Credentials** | API keys, tokens, .env paths in code | Move to env vars |
| **External Script Fetching** | `curl | bash` patterns | Replace with documented install |
| **YARA malware matches** | Code that matches info-stealer/backdoor | Manual code review |

## Step 4: Fix Real Issues

### Fix shell=True danger
```python
# BAD
subprocess.Popen(server['cmd'], shell=True, ...)

# GOOD
import shlex
cmd_list = shlex.split(server['cmd'])
# Handle cd && cmd pattern
if '&&' in server['cmd'] and server['cmd'].startswith('cd '):
    parts = server['cmd'].split('&&', 1)
    cd_dir = parts[0].strip()[3:].strip()
    cmd_list = shlex.split(parts[1].strip())
    subprocess.Popen(cmd_list, cwd=cd_dir, shell=False, ...)
else:
    subprocess.Popen(cmd_list, shell=False, ...)
```

### Fix CVE dependencies
For each requirements.txt / package.json:
```bash
# Check latest versions
npm view <pkg> version   # for JS
pip index versions <pkg> # for Python

# Pin to latest or >= patched version
# pillow>=11.2.0, requests>=2.32.0, etc.
```

### Fix unpinned deps
In package.json: `"dep": "^x.y.z"`
In requirements.txt: `dep>=x.y.z`

## Step 5: Verify

Re-scan fixed skills to confirm issues are resolved:

```bash
skillspector scan ~/AppData/Local/hermes/skills/community/<fixed-skill>/ --no-llm
```

Check specifically:
- shell=True issues downgraded to "Popen (no shell=True"
- CVE pinning recognized
- Unpinned count reduced

## Pitfalls

1. **SkillSpector does NOT properly resolve `>=` version constraints** — it may still flag "Unpinned" even with `>=x.y.z`. This is a scanner limitation, not a real issue.
2. **Binary files in skills** (fonts, PDFs) will always trigger false positives. Add them to `.gitignore` or exclude from scans.
3. **OSV.dev rate limits** — the scanner truncates vulnerability lookups at 10 per batch. Multi-pass may be needed for large scans.
4. **Some skills will always score 100/100** due to subprocess usage, which is legitimate for automation skills.
5. **Windows paths** — SkillSpector saves reports to `C:\Users\<user>\AppData\Local\Temp\` on Windows, not `/tmp/`.
6. **The scanner categorizes LICENSE files as Scope Creep** — always false positive, skip.
7. **shell=True fix requires understanding cmd structure** — read the full file first; some commands use `cd && cmd` patterns that need `cwd=` parameter.

## Reporting Preferences

For maintenance/audit jobs sent to this user:

- Use Chinese-first wording; keep English only for product names, package names, model IDs, commands, and error identifiers.
- Use plain Markdown headings, tables, and bullets.
- Avoid decorative separator bars such as `━━━━━━━━` or `════════`.
- If the job posts to Telegram topics, explicitly set the target chat and `message_thread_id`; do not rely on generic home-channel env vars when the user provided a topic URL.

## Purge Temp Files After Audit

```bash
rm -f /tmp/community_scan.json /tmp/*_verify.json
```
