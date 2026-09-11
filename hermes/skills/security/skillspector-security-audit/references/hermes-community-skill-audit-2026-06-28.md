# Hermes Community Skill Audit — 2026-06-28

Session-specific notes from auditing the local Hermes community skill library with NVIDIA SkillSpector.

## Environment

- Host: Windows 11, git-bash shell.
- Skill directory scanned: `~/AppData/Local/hermes/skills/community/`.
- SkillSpector: v2.2.3, installed from GitHub in a Python 3.12 uv venv.
- Working command:

```bash
cd /tmp
git clone https://github.com/NVIDIA/SkillSpector.git
uv venv --python 3.12 skillspector-venv-py312
source skillspector-venv-py312/Scripts/activate
uv pip install ./SkillSpector
skillspector scan ~/AppData/Local/hermes/skills/community/ --no-llm --format json -o /tmp/community_scan.json
```

## Results

- 70 community skills scanned.
- 1910 total findings.
- About 1609 were false positives.
- Roughly 301 findings were actionable or needed manual review.

## High-confidence false-positive classes

These should be triaged before editing files:

- Binary assets (`.ttf`, `.otf`, `.pdf`, images) flagged as context stuffing/tool abuse.
- XML/XSD/CSProj comments flagged as hidden instructions.
- `sudolewis@gmail.com` or similar text flagged as `sudo` command chaining.
- `keychain` in image-prompt/style libraries flagged as credential access.
- `os.environ.copy()` flagged as environment harvesting when used to build subprocess env.
- `capture_output=True` flagged as output injection in ordinary subprocess probes.
- LICENSE files flagged as scope creep.
- Security-audit skills mentioning `social-engineering` flagged by YARA.

## Real fixes performed

- Replaced `subprocess.Popen(..., shell=True)` in `anthropic-webapp-testing/scripts/with_server.py` with `shlex.split()`, `shell=False`, and a `cd <dir> && <cmd>` compatibility path using `cwd=`.
- Updated vulnerable Python dependency floors:
  - `pillow>=11.2.0`
  - `numpy>=2.2.0`
  - `requests>=2.32.0`
  - `python-dotenv>=1.1.0`
  - `pymupdf>=1.25.5`
  - `mcp>=1.7.0`
  - `anthropic>=0.56.0`
  - `python-docx>=1.1.2`
  - `mammoth>=1.9.0`
- Updated JS dependency constraints:
  - `ws>=8.18.4`
  - `markdown-it^14.2.0`

## Verification caveat

SkillSpector v2.2.3 may still report `Unpinned Dependencies` or CVE findings even after using safe `>=` constraints. Treat those residual findings as scanner limitations only after reading the actual file and confirming the floor version is safe.

## Reporting preference learned

When reporting maintenance-task output to this user, keep it Chinese-first and plain Markdown. Avoid decorative separator bars such as `━━━━━━━━`; retain necessary English only for product names, model IDs, package names, and commands.
