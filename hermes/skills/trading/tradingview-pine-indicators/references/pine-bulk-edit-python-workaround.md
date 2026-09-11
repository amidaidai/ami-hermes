# Pine Script Bulk Edit via Python (Patch Escape-Drift Workaround)

## When to use this

Hermes' `patch` tool frequently fails with "Escape-drift detected" on Pine Script edits that contain literal `\"` sequences (common in `input.*()` tooltips, `str.replace()`, label strings, and alert messages). The tool interprets Pine's backslash-quote as a JSON-level escape and refuses to match.

Use a Python terminal script instead when:
- The edit spans 5+ lines.
- Any line contains `\"` or nested quotes.
- You are doing a multi-step refactor and need transactional safety.
- `patch` failed twice on the same region.

## Workflow

1. **Backup the source** before any edits.
2. **Read the file in Python**, perform string or line replacements in memory.
3. **Write back** and verify with `grep`.
4. **Count outputs / dead identifiers** after each batch.

## Minimal example

```python
import shutil, re

src = 'C:/Users/Administrator/Desktop/指标svp_v10.txt'
backup = 'C:/Users/Administrator/AppData/Local/Temp/svp_v10_backup.txt'
work = 'C:/Users/Administrator/AppData/Local/Temp/svp_v10_work.txt'

shutil.copy(src, backup)
shutil.copy(src, work)

with open(work, 'r', encoding='utf-8') as f:
    text = f.read()

# Example: remove duplicated module prefix from action-panel value builder
old = 'string actionIctText = sweptLowReclaimed ? "ICT " + lastEventName + "收回"'
new = 'string actionIctText = sweptLowReclaimed ? lastEventName + "收回"'
text = text.replace(old, new)

with open(work, 'w', encoding='utf-8') as f:
    f.write(text)

# Verification
print('plot count:', len(re.findall(r'\bplot\s*\(', text)))
print('table count:', len(re.findall(r'\btable\.new\s*\(', text)))
```

## Line-based replacement for long blocks

When exact string matching fails due to whitespace or mixed encodings, replace by line indices:

```python
with open(work, 'r', encoding='utf-8') as f:
    lines = f.readlines()

start = next(i for i, l in enumerate(lines) if l.strip().startswith('string actionLine1 ='))
end = next(i for i in range(start, len(lines)) if lines[i].strip().startswith('string actionText ='))

new_block = '''string actionLine1 = "结论：" + actionStateText + " · " + actionSentimentText
...'''

lines = lines[:start] + [new_block] + lines[end+1:]

with open(work, 'w', encoding='utf-8') as f:
    f.writelines(lines)
```

## Verification checklist after each batch

- `grep -cE "^\s*.*\bplot\b|^\s*.*\bfill\b|^\s*.*\bbgcolor\b|^\s*table\.new"` — output series count.
- `grep -c "Undeclared"` — only useful after TV compile; locally check that every new variable is referenced.
- `grep -c <removed_identifier>` — confirm zero residuals after feature removal.
- Bracket/parenthesis balance sanity check:
  ```python
  print(text.count('(') - text.count(')'))
  print(text.count('{') - text.count('}'))
  ```

## Delivery

Copy the final work file to `C:/Users/Administrator/Desktop/<name>.txt` and share that path. Do not deliver the web UI upload path directly.
