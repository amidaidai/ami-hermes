---
name: skill-security-audit
description: "Skill Security Grading & Audit Framework — pre-deploy security checks, vulnerability scanning, quality scoring for agent skills, based on Agent Skills Hub methodology"
version: 1.0.0
author: Hermes Agent
tags: [security, audit, skills, quality, vulnerability]
---

# Skill Security Audit Framework

Security-graded approach for evaluating and auditing AI agent skills before deployment. Based on the Agent Skills Hub methodology (10 quality dimensions, 8-hour refresh cadence).

## Security Statistics
- **26.1% of agent skills contain security vulnerabilities** (Liu et al., 2026, n=31,132 skills)
- Source: [arxiv.org/abs/2601.10338](https://arxiv.org/abs/2601.10338)

## 10 Quality Scoring Dimensions

| Dimension | Weight | Description |
|-----------|--------|-------------|
| Stars | 15% | GitHub stars (popularity signal) |
| Maintenance | 15% | Recent commits and release cadence |
| Documentation | 12% | README quality, API docs completeness |
| Code Quality | 12% | Linting, type coverage, test coverage |
| Security | 12% | Vulnerability scan results (CVE, SCA, SAST) |
| Dependencies | 10% | Known vulnerabilities in transitive deps |
| License | 8% | License compatibility and clarity |
| Compatibility | 8% | Works with target agent framework |
| Community | 5% | Issues/PRs responsiveness, forks |
| Activity | 3% | Recent activity (last 90 days) |

## Pre-Deploy Audit Checklist

### Static Analysis
- [ ] Scan code for hardcoded secrets/API keys
- [ ] Check for shell injection vectors in terminal/exec calls
- [ ] Verify all HTTP requests use HTTPS
- [ ] Check for `eval()`, `exec()`, `os.system()` usage
- [ ] Validate file path traversal protection
- [ ] Review environment variable access

### Dynamic Analysis
- [ ] Run in sandbox/isolated environment first
- [ ] Verify data exfiltration protections
- [ ] Test with mock APIs before real credentials
- [ ] Check error handling doesn't leak sensitive info

### Supply Chain
- [ ] Audit all npm/Python dependencies for CVEs
- [ ] Check dependency freshness (< 1 year since update)
- [ ] Verify package signing (npm provenance, PyPI attestations)
- [ ] Review `postinstall` scripts in npm packages

### Compliance (Enterprise)
- [ ] SOC 2 alignment
- [ ] ISO/IEC 42001 (AI management)
- [ ] EU AI Act risk classification
- [ ] GDPR data handling

## Using `skillspector-security-audit`
Load the dedicated `skillspector-security-audit` skill from the security category for scanning community skills with NVIDIA SkillSpector.

## Workflow
1. Before installing any public skill, run security audit
2. Check quality score on Agent Skills Hub or compute manually
3. Audit critical dimensions (security, dependencies, code quality)
4. Only install audited and verified skills into production
5. Re-audit every 30 days or on skill update
