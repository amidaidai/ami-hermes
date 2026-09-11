# NVIDIA SkillSpector — Automated Security Scanner for Agent Skills

**Version:** 2.2.3 (Apache 2.0)  
**Source:** https://github.com/NVIDIA/SkillSpector  
**Python:** 3.12+  
**Research Base:** Liu et al., 2026 — 26.1% of skills contain vulnerabilities, 5.2% show likely malicious intent

## Overview

SkillSpector performs two-stage analysis on AI agent skill directories:

1. **Static analysis** — 64 vulnerability patterns across 16 categories, run without network (except SC4 OSV.dev CVE lookup)
2. **Optional LLM analysis** — Semantic evaluation via OpenAI/Anthropic/NVIDIA models for deeper context-aware findings

## Installation (no Docker)

```bash
git clone https://github.com/NVIDIA/SkillSpector.git
cd SkillSpector
uv venv .venv-py312 && source .venv-py312/Scripts/activate  # Windows git-bash
uv pip install .
```

Requires Python 3.12+. On Windows with `uv`, use `uv venv --python 3.12 .venv`.

## Quick Usage

```bash
# Static analysis only (fastest, no API keys needed)
skillspector scan ./path/to/skill/ --no-llm

# With LLM semantic analysis
export SKILLSPECTOR_PROVIDER=openai
export OPENAI_API_KEY=sk-...
skillspector scan ./path/to/skill/

# Output formats
skillspector scan ./path/ --no-llm --format json -o report.json
skillspector scan ./path/ --no-llm --format markdown -o report.md
skillspector scan ./path/ --no-llm --format sarif -o report.sarif
```

## 16 Detection Categories (64 patterns)

| Category | Patterns | Key Severities |
|----------|----------|---------------|
| Prompt Injection | 5 | P5 Harmful Content (CRITICAL), P1 Instruction Override (HIGH) |
| Data Exfiltration | 4 | E2 Env Variable Harvesting (HIGH) |
| Privilege Escalation | 3 | PE3 Credential Access (HIGH) |
| Supply Chain | 6 | SC4 Known Vulnerable Dependencies (HIGH), SC2 External Script Fetch (HIGH) |
| Excessive Agency | 4 | EA1 Unrestricted Tool Access (HIGH), EA2 Autonomous Decision Making (HIGH) |
| Output Handling | 3 | OH1 Unvalidated Output Injection (HIGH) |
| System Prompt Leakage | 3 | P6 Direct Prompt Extraction (HIGH) |
| Memory Poisoning | 3 | MP1 Persistent Context Injection (HIGH) |
| Tool Misuse | 3 | TM1 Tool Parameter Abuse (HIGH) |
| Rogue Agent | 2 | RA1 Self-Modification (CRITICAL) |
| Trigger Abuse | 3 | TR2 Shadow Command Trigger (HIGH) |
| Behavioral AST | 8 | AST1 exec() Call (CRITICAL) |
| Taint Tracking | 5 | TT3 Credential Exfiltration Chain (CRITICAL) |
| YARA Signatures | 4 | YR1 Malware Match (CRITICAL) |
| MCP Least Privilege | 4 | LP1 Underdeclared Capability (HIGH) |
| MCP Tool Poisoning | 4 | TP1 Hidden Instructions (HIGH) |

## Risk Scoring

- CRITICAL issue: +50 points
- HIGH issue: +25 points
- MEDIUM issue: +10 points
- LOW issue: +5 points
- Executable scripts: ×1.3 multiplier
- Score capped at 100

**Interpretation:**
- 0-20 LOW → SAFE (some informational findings)
- 21-49 MEDIUM → CAUTION (review highlighted issues)
- 50-99 HIGH → DO NOT INSTALL without thorough review
- 100 CRITICAL → DO NOT INSTALL (confirmed dangerous patterns)

## Known False Positive Patterns

From experience scanning 70 Hermes community skills:

1. **Context Window Stuffing (MP2)** — Fires on large markdown template files, font files, and reference docs. These are not actual stuffing attacks, just large content blocks. **Ignore when file is static content/template only.**
2. **Session Persistence (RA2)** — Fires on config/setup instructions that mention state files. Legitimate when skill stores user preferences with explicit consent.
3. **Unpinned Dependencies (SC1)** — Markdown files mentioning packages without version pinning. Not a real supply chain risk unless there's an actual install script/requirements.txt.
4. **Scope Creep (EA3)** — Skills that reference multiple toolsets or capabilities. Common in multi-purpose skills; cross-reference with actual code behavior.

## LLM Providers

| Provider (`SKILLSPECTOR_PROVIDER`) | Credential | Default Model |
|---|---|---|
| `openai` | `OPENAI_API_KEY` (+ optional `OPENAI_BASE_URL`) | `gpt-5.4` |
| `anthropic` | `ANTHROPIC_API_KEY` | `claude-opus-4-6` |
| `nv_build` | `NVIDIA_INFERENCE_KEY` | `deepseek-ai/deepseek-v4-flash` |

Works with local servers (Ollama, vLLM, llama.cpp) via OpenAI-compatible endpoint.

## Usage in Security Review Workflow

When evaluating a new skill for installation:

1. **First pass:** `skillspector scan ./skill/ --no-llm` — get risk score and pattern hits
2. **Filter known FPs:** Review each issue against the false positive patterns above
3. **Deep dive on real hits:** Focus on CRITICAL/HIGH issues in actual code files (not markdown)
4. **LLM pass (optional):** Add `--llm` for semantic analysis on ambiguous findings
5. **Manual verification:** Cross-check credential access, external transmission, and subprocess calls manually by reading the flagged source lines
6. **Report:** Use the JSON output (`--format json`) to integrate into structured reports
