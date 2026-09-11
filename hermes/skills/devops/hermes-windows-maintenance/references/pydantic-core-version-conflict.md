# pydantic-core version conflict — observed transcript (2026-08-29)

## Incident summary
User: "为什么我切换模型不成功，而且好多的东西都被改了" (model switching fails + lots of config got changed).
Root cause found: `pydantic-core` 2.48.0 was pip-installed into the hermes venv (18:21) while
`pydantic` 2.13.4 stayed pinned (requires pydantic-core 2.46.4). Every NEW Hermes process crashed
at import; the long-running Web UI session survived (modules already in memory).

## Symptom signatures
1. `hermes doctor` partial crash — pydantic import raises SystemError:
   ```
   File "...\venv\Lib\site-packages\pydantic\version.py", line 94, in _ensure_pydantic_core_version
   raise SystemError(
   SystemError: The installed pydantic-core version (2.48.0) is incompatible with the current
   pydantic version, which requires 2.46.4.
   ```
2. `./venv/Scripts/python -c "import pydantic_core, pydantic"` → same SystemError.
3. `ls venv/Lib/site-packages/ | grep -i pydantic_core` shows BOTH:
   - `pydantic_core-2.46.4.dist-info` (older)
   - `pydantic_core-2.48.0.dist-info` (newer — the collision)
4. `pip show pydantic-core` may report the OLD version (2.46.4) because dist-info metadata is
   ambiguous — trust the `import` result, not pip show.
5. errors.log fills with MCP failures: `Failed to connect to MCP server 'binance' (command=python):
   Connection closed` — same root cause (server.py can't import pydantic).
6. Gateway log shows normal activity for the OLD session (it survives), while new bridge runs die.

## Fix (exact commands that worked)
```bash
cd /c/Users/Administrator/AppData/Local/hermes/hermes-agent
./venv/Scripts/python -m pip install --force-reinstall --no-deps "pydantic-core==2.46.4"
rm -rf venv/Lib/site-packages/pydantic_core-2.48.0.dist-info
```

## Verification (all passed)
```bash
./venv/Scripts/python -c "import pydantic_core, pydantic, openai; print('OK', pydantic.__version__, pydantic_core.__version__)"
# OK 2.13.4 2.46.4
./venv/Scripts/python -c "import hermes_cli.config; print('hermes_cli import OK')"
hermes doctor   # all green
```

## Config restore that went with it (model routing was also changed)
`hermes config set model.default deepseek-v4-flash-vision-exp` + `hermes config set model.provider deepseek`
restored the intended default. The broken default had been `gpt-5.6-luna / opencode-go` (provider
returning HTTP 500). Config backups: `config.yaml.bak.20260829_181943` / `config.yaml.bak` showed
the diff. Also `jobs.json.bak.pre-restore.20260829` in `cron/` flagged a cron restore event.

## Lesson
- Never casually `pip install` into the hermes venv — pyproject.toml pins pydantic==2.13.4 with a
  comment explaining WHY (OpenAI-SDK segfault fix that required pydantic-core 2.46.4).
- "Model switching doesn't work" can be a venv native-lib breakage, not a config issue — check
  `hermes doctor` FIRST before touching model config.
- Old-process-alive / new-process-crash asymmetry = in-memory module cache vs fresh import.
