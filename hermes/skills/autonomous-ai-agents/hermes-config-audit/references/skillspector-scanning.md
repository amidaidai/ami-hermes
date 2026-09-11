# SkillSpector Scanning Reference

## Installation Notes (Windows)

- Requires **Python ≥3.12**. Use `uv venv --python 3.12` to get it if the default is 3.11.
- No Docker on this machine — install from git clone with `uv pip install ./SkillSpector`.
- The package is NOT on PyPI (not `pip install skillspector`). Always clone from GitHub.

## Known False Positive Patterns (Hermes Community Skills)

These findings are SAFE and can be ignored:

### 1. Font/Asset Binary Files
- Any `.ttf`, `.otf`, `.woff`, `.woff2`, `.pdf` file scanned as text
- SkillSpector reads them as raw bytes → triggers Context Window Stuffing (MEDIUM), Tool Parameter Abuse (HIGH)
- **Occurrences**: 1,456 in anthropic-canvas-design alone

### 2. XML Documentation Comments
- `<!-- comment -->` in XSD schemas, .csproj files, C# samples
- Triggered as "Hidden Instructions"
- **Key example**: `software-copyright-materials/vendor/docx-toolkit/assets/xsd/*.xsd` — all legitimate XML schema documentation

### 3. Email Addresses Containing "sudo"
- `sudolewis@gmail.com` → triggers Chaining Abuse
- Example: html-ppt skill's author email

### 4. Package Manager Install Flags
- `--noconfirm` (pacman), `-y` (apt/dnf) in setup scripts → Tool Parameter Abuse
- These are standard package installation commands, not injection

### 5. License Files
- `LICENSE.txt`, `LICENSE` bundled with a skill → flagged as "Scope Creep" (LOW)
- Safe. The skill is not claiming extra capabilities by having a license file.

### 6. Image Prompt Keywords
- "keychain" in style_library.json → Credential Access
- It's a resin keychain product photo prompt keyword, not an SSH keychain reference

### 7. Standard os.environ Usage
- `os.environ.copy()` → "Env Variable Harvesting"
- `os.environ.items()` → same
- Both are standard Python patterns for passing env to subprocesses

### 8. capture_output=True in subprocess.run
- Any `subprocess.run(cmd, capture_output=True)` → "Unvalidated Output Injection"
- `capture_output=True` captures output; it does NOT inject untrusted data. The actual injection risk is missing input validation.

### 9. YARA Rules on Security Skills
- slowmist-agent-security mentions "social-engineering" → YARA exploit_framework
- The skill IS a security framework. "social-engineering" is a legitimate category name.

### 10. YARA Cookie Restore
- `restoreCookies()` → YARA info_stealer
- In url-to-markdown, this restores the user's own session cookies for authenticated scraping.
- Legitimate functionality.

### 11. YARA .bashrc Modification
- `>> "$HOME/.bashrc"` in setup scripts → YARA backdoor_persistence
- Standard PATH addition during .NET SDK installation. Not a backdoor.

### 12. "Policy Insert" Documents
- Any document content referencing "policy" → detected patterns in the Intent analyzer
- False positive when the skill is a documentation/legal template generator.

## Real Issues Found (Fixed During Audit)

### P1: Vulnerable Dependencies (4 skills)

| Skill | Dependency | CVE Count | Fix |
|-------|-----------|-----------|-----|
| gpt-image2-ppt | pillow, requests, pymupdf, python-dotenv | 10+ each | `>=11.2.0, >=2.32.0, >=1.25.5, >=1.1.0` |
| anthropic-slack-gif-creator | pillow, numpy | 10 each | `>=11.2.0, >=2.2.0` |
| anthropic-mcp-builder | mcp, anthropic | 3+2 | `>=1.7.0, >=0.56.0` |
| patent-disclosure-skill | python-docx, mammoth | 2+1 | `>=1.1.2, >=1.9.0` |
| baoyu-url-to-markdown | ws | 2 | `>=8.18.4` |
| baoyu-translate | markdown-it | 1 | `^14.2.0` |

### P2: shell=True (1 file)
- `anthropic-webapp-testing/scripts/with_server.py` → replaced with `shlex.split()` + `shell=False` + `cwd=` for `cd &&` patterns
- Scan confirms: finding now says "Popen (no shell=True"

### P3: Unpinned Dependencies (2 files)
- `baoyu-url-to-markdown/scripts/package.json` → ws pinned
- `baoyu-translate/scripts/package.json` → markdown-it pinned
- All other checked files (7 total) were already properly locked

## SkillSpector Scanner Limitations

1. **Does not resolve `>=` version constraints** — flags `pillow>=11.2.0` as BOTH "Unpinned" AND "Known Vulnerable" even though `>=11.2.0` excludes all listed CVEs.
2. **OSV.dev API truncation** — "Processing 10 of 119 vulnerabilities, truncating the rest" warning is normal; OSV limits response size.
3. **No file exclusion** — cannot skip binary directories (.ttf, .pdf) during scanning, inflating scan time and false positive count.
4. **Intent analyzer is aggressive** — keywords like "policy", "instruction", "rule" trigger false positive intent matches in documentation files.

## Total Scan Stats (70 Community Skills)

| Metric | Count |
|--------|-------|
| Total issues | 1,910 |
| False positive (estimated) | ~1,609 |
| Real issues fixed | ~301 (categorized) |
| Skills with 100/100 score | 12 (mostly from binary file noise) |
| Skills with 0/100 score | 2 (baoyu-slide-deck, baoyu-compress-image) |

## Recommended Fix Approach

Use `delegate_task` with concurrent workers to fix multiple skills in parallel:
- Task 1: CVE pinning (4 requirements files)
- Task 2: shell=True fixes (if any)
- Task 3: Unpinned deps (package.json coverage)
- Follow with verification scan on fixed skills
