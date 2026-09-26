---
name: pptx-production-pipeline
description: "Full Windows pipeline for generating professional PPTX decks: read source docs (.doc/.docx/.pptx), generate with pptxgenjs, convert to PDF via comtypes, visual QA with PyMuPDF + vision. Complements the bundled 'powerpoint' skill with Windows-specific tooling and legacy file handling."
---

> **同族导航** — 演示/PPT 组 8 个技能，先按**产出物**选路，别加载错（同族入口：`gov-presentation-creation`）
> · **本技能 `pptx-production-pipeline`** = 通用 PPTX 全流程（读源文档→pptxgenjs 生成→Windows 转换/QA）
> · 政府/公文类：`gov-presentation-creation`（政府/官方中文演示 · 公文语态与政策核查（用户首选路线））、`official-ppt-generation`（政府/官方培训 PPT 生成器 + QA）
> · 通用 PPTX 管线：`pptx-production-pipeline`（通用 PPTX 全流程（读源文档→pptxgenjs 生成→Windows 转换/QA））⭐、`powerpoint`（python-pptx 读写编辑 .pptx（非生成管线））
> · 网页 HTML 演示：`html-ppt`（网页 PPT（多风格/动画，HTML 交付））、`guizang-ppt-skill`（横向翻页网页 PPT（单 HTML + WebGL））
> · 图像优先：`ppt-image-first`（图像优先：先定视觉方向再做页）、`gpt-image2-ppt`（图像优先：gpt-image-2 出高分辨率页再拼 PPTX）
> · 组内成员互斥度低，同时加载会互相抢触发词；改一个就同步其余。


# PPTX Production Pipeline (Windows)

End-to-end workflow for producing polished, data-rich presentation decks on Windows when you have real content (government docs, data tables, policy research) and need visual QA before delivery.

## When to use

- Creating a multi-slide PPTX from structured data + policy research + local images
- Need to read legacy `.doc` files (not `.docx`) as input
- Need PPTX→PDF conversion on Windows where LibreOffice is absent but PowerPoint is installed
- Need to visually QA slides before delivery (render to images, inspect with vision)
- The bundled `powerpoint` skill's Linux-centric toolchain (soffice, pdftoppm) doesn't apply

## When NOT to use

- Quick single-slide edits → use `powerpoint` skill directly
- HTML-based presentations → use `html-ppt` or `guizang-ppt-skill`
- AI-image-first slides → use `gpt-image2-ppt`
- macOS/Linux environments → use `powerpoint` skill (soffice + pdftoppm)

## Pipeline Overview

```
1. Gather content  →  2. Read source files  →  3. Generate PPTX  →  4. Convert to PDF  →  5. Render images  →  6. Visual QA  →  7. Fix + re-export
```

## Step 1: Gather Content

- Search web for current policy/data using `web_search` + `web_extract`
- Read user-provided attachments (`.doc`, `.docx`, `.pdf`, images)
- **Check for existing generation scripts and preprocessed assets** in the working directory before starting from scratch. Look for:
  - `src/generate_ppt.js` or similar Node.js scripts that build with pptxgenjs
  - `assets/prepared/` directory with pre-cropped/cover images already processed by sharp
  - `package.json` with pptxgenjs and sharp dependencies
  - Existing `output/` with prior PPTX/PDF/QA renders
  If these exist, **verify script data against user-provided latest figures** before regenerating. Reuse the existing script if data matches; patch only changed figures, dates, and slide content. Do not rebuild the entire 40-slide template from scratch when a working script is already in place.
- Organize local image assets in an `assets/` directory
- **All images must be real local photos** — never AI-generated for government/official training materials

## Step 2: Read Source Files

### `.docx` files
```bash
python -m markitdown "file.docx"
```

### `.pptx` files (text extraction)
```bash
python -c "from markitdown import MarkItDown; print(MarkItDown().convert('file.pptx').text_content)"
```

### Legacy `.doc` files (markitdown CANNOT read these)

**Option A — antiword** (fast, clean output, but fails on WPS-created docs):
```bash
antiword "file.doc"
```
antiword is available in MSYS2/git-bash at `/mingw64/bin/antiword`.

**Option B — olefile + struct** (fallback when antiword says "not a Word Document"):
```python
import olefile, struct, re
ole = olefile.OleFileIO('file.doc')
wd = ole.openstream('WordDocument').read()
fc_min = struct.unpack_from('<I', wd, 0x18)[0]  # text start offset
fc_mac = struct.unpack_from('<I', wd, 0x1C)[0]  # text end offset
text_bytes = wd[fc_min:fc_mac]
text = text_bytes.decode('utf-16-le', errors='ignore')
readable = re.findall(r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef\w\s.,;:!?()【】《》、。；：！？（）\-\—\%\"\'/]+', text)
result = ''.join(readable)
```
See `references/doc-file-reading.md` for full details and edge cases.

## Step 3: Generate PPTX with pptxgenjs

Use Node.js + `pptxgenjs` + `sharp` (for image preprocessing).

### Project setup
```json
// package.json
{
  "dependencies": {
    "pptxgenjs": "^4.0.1",
    "sharp": "^0.35.3"
  }
}
```

### Key design principles (from powerpoint skill, reinforced)

1. **Pick a bold, content-informed color palette** — not generic blue. For government/agriculture: forest green + gold + navy works well.
2. **Dominance over equality** — one color 60-70% weight, 1-2 supporting, one sharp accent.
3. **Dark/light sandwich** — dark covers + section dividers, light content slides.
4. **Every slide needs a visual element** — image, chart, icon, or shape. No text-only slides.
5. **Vary layouts** — don't repeat the same column structure across consecutive slides.
6. **NEVER use accent lines under titles** — hallmark of AI-generated slides.
7. **Commit to a visual motif** — e.g., colored left-border accent bars, repeated across all slides.

### Helper functions pattern

Build reusable helpers: `addText`, `rect`, `line`, `image`, `addFooter`, `addTitle`, `tag`, `metric`, `bulletList`, `callout`, `hBar`, `sectionDivider`. See `templates/generate_ppt_template.js` for a proven structure.

### Editing an existing script (incremental updates)

When a working script exists (e.g., `src/generate_ppt.js` from a prior generation), prefer incremental patches over rebuilding:

1. **Patch data values** — locate the exact text string and replace with updated figures using `patch` (mode='replace'). Preserve precision: `84.1162万亩` not `"约84万亩"`.
2. **Insert new slides** — find a unique comment marker (e.g., `// 18 Situation judgement`) in the script and insert new slide blocks before the marker using `patch`.
3. **Insert mid-file blocks safely** — when adding multi-line blocks that include template literals (backticks) or braces, use `write_file` with the entire updated file rather than `patch` to avoid brace-matching errors.
4. **Verify n counter** — the slide counter `n` auto-increments; inserting new slides before existing ones does NOT require renumbering — the counter handles it. But speaker notes referencing "slide X" may need manual update.
5. **Add new source URLs** — append to the `SRC` object at the top of the script, then reference them in new slides.
6. **Re-run and re-QA only affected sections** — after patching, regenerate the PPTX, re-render to images, and run `vision_analyze` on the new/updated slides plus their neighbors to catch overflow from layout changes.

### Image preprocessing with sharp
```javascript
const sharp = require('sharp');
async function prepImage(srcName, outName, width, height, position = 'centre', quality = 88) {
  await sharp(path.join(ASSETS, srcName))
    .rotate()
    .resize(width, height, { fit: 'cover', position })
    .jpeg({ quality, mozjpeg: true })
    .toFile(path.join(PREP, outName));
}
```

## Step 4: Convert PPTX to PDF (Windows)

The `powerpoint` skill recommends LibreOffice (`soffice`), but on Windows with PowerPoint installed, use COM automation:

```python
import comtypes.client, os

pptx_path = os.path.abspath('output/deck.pptx')
pdf_path = os.path.abspath('output/deck.pdf')

powerpoint = comtypes.client.CreateObject('Powerpoint.Application')
powerpoint.Visible = 1
deck = powerpoint.Presentations.Open(pptx_path)
deck.SaveAs(pdf_path, 32)  # 32 = ppSaveAsPDF
deck.Close()
powerpoint.Quit()
```

**Prerequisite:** `pip install comtypes` and PowerPoint must be installed.

See `references/windows-pdf-conversion.md` for troubleshooting.

## Step 5: Render PDF to Images

The `powerpoint` skill uses `pdftoppm` (poppler), which is often not installed on Windows. Use PyMuPDF instead:

```python
import fitz  # PyMuPDF
import os

doc = fitz.open('output/deck.pdf')
qa_dir = 'assets/qa'
os.makedirs(qa_dir, exist_ok=True)

for i, page in enumerate(doc, 1):
    pix = page.get_pixmap(dpi=130)
    pix.save(os.path.join(qa_dir, f'slide-{i:02d}.jpg'))

doc.close()
```

**Prerequisite:** `pip install pymupdf`

## Step 6: Visual QA

Use `vision_analyze` to inspect key slides. **Always inspect at minimum:**

1. **Cover slide** — title readability, image quality, alignment
2. **Data-dense slides** — text overflow, element overlap, chart readability
3. **Table slides** — cell text fit, row alignment, header contrast
4. **Closing slide** — text contrast against background image (common failure point)

### QA prompt pattern
```
Check this slide for: text overflow, element overlap, readability of all text, alignment issues. Report any problems.
```

### Common issues found in QA

| Issue | Fix |
|-------|-----|
| Light gray text on semi-transparent white over bright photo | Use opaque white background + dark bold text (`color: '3A3A3A', bold: true`) |
| Text inside colored bars lacks padding | Offset text x-position by 0.2" from bar edge |
| Orange "surplus" segments not proportional | These are labels, not charts — keep consistent size |
| Secondary text on photo-overlay slides washes out | Remove transparency on white text containers (`transparency: 0`) |

## Step 7: Fix and Re-verify

1. Fix issues in the generation script
2. Re-run `node generate_ppt.js`
3. Re-convert to PDF
4. **Re-render only affected slides** for verification:
```python
doc = fitz.open(pdf_path)
pix = doc[slide_number - 1].get_pixmap(dpi=130)
pix.save(f'assets/qa/slide-{slide_number:02d}.jpg')
doc.close()
```
5. Re-inspect with vision_analyze

## Writing Style for Government/Official Content

When generating PPT content for government training, official briefings, or administrative materials, the text register must match the domain. AI-generated slides in government contexts are immediately rejected by users when they use consulting/corporate language patterns.

### Banned patterns (user explicitly rejected these)

| Pattern | Example | Fix |
|---------|---------|-----|
| Coined catchy framework names | "五重压力叠加期" "作战图" "安全垫" "六类困难" | Use plain descriptive nouns: "当前面临的主要形势" "年度重点工作安排" |
| Slogans as titles | "底数要清" "政策要准" "先把四件事做起来" | Use noun-phrase titles: "耕地保护基本情况" "下一步工作要求" |
| "不是…而是…" rhetorical construction | "不是新增建设指标，而是安全垫" | State facts directly: "该余量为年度考核结果，不作为建设用地指标" |
| Exclamation marks / imperative voice | "先做真恢复、能耕种、管得住的3000亩！" | Use declarative: "本年度恢复任务应优先选择具备稳定耕作条件的地块" |
| Consulting-style analysis labels | "三优先" "红黄绿管理" "周循环" "系统战" "硬约束" "闭环要硬" | Use standard administrative terms: "工作优先序" "进度管理" "工作推进机制" |
| Colloquial subheadings | "不是'任务重'三个字可以概括" | Use formal: "存在的主要困难" |
| "不能…""严禁…" in callout bodies | "不能只清表、旋耕、临时撒种" | Use positive requirements: "应核实灌排条件、土壤状况和后续管护安排" |

### Correct register for government PPT

- **Titles**: Noun phrases or prepositional phrases. "耕地保护基本情况" not "底数要清". "政策法规变化与面临形势" not "政策要准".
- **Body text**: Declarative sentences, present tense. "全县耕地空间划定85.4401万亩" not "划足、留余、把恢复潜力落到图上".
- **Callouts**: State the requirement or fact, not the anti-pattern. "年度变更调查结果应保持持续稳定" not "不能依赖年末突击恢复".
- **Section dividers**: Brief formal subtitle describing scope. "耕地保护目标完成情况、空间划定及遥感监测" not "先把考核任务、规划划定、年度监测三种口径分开".
- **Notes (speaker notes)**: Professional lecturer tone, concise. "本页数据来源为2025年度考核结果" not "讲解重点：超额只能说明当前有一定安全垫".
- **Policy references**: Always use full document title + 文号. "《中共中央办公厅 国务院办公厅关于加强耕地保护提升耕地质量完善占补平衡的意见》" not "2024年两办《意见》".

### General principle

If a phrase sounds like it could be in a McKinsey deck or a tech startup pitch, it does not belong in a government training PPT. Government PPTs use flat, descriptive, administrative language. The audience is镇村干部 (township and village cadres), not executives.

## Pitfalls

- **AI-style writing in government PPTs** — users will reject the entire deck. See "Writing Style for Government/Official Content" section above. Always use formal administrative register, never consulting/corporate language patterns.
- **markitdown cannot read `.doc` files** — only `.docx`. Use antiword or olefile fallback.
- **antiword fails on WPS-created `.doc` files** with "not a Word Document" error. Use olefile + struct.unpack to extract UTF-16LE text directly from the WordDocument stream.
- **pdftoppm/poppler not available on Windows** — use PyMuPDF (`fitz`) instead. Install: `pip install pymupdf`.
- **LibreOffice not installed on Windows** — use comtypes + PowerPoint COM for PDF conversion.
- **Semi-transparent white boxes over bright photos** — secondary text becomes unreadable. Either make boxes fully opaque or use dark bold text.
- **pdf2image requires poppler in PATH** — don't use pdf2image on Windows unless poppler is installed. PyMuPDF has no external dependencies.
- **python3 not found in MSYS2/git-bash** — use `python` (not `python3`) on Windows. The Hermes venv python is at the path shown in terminal output.
- **`addTable` header duplication bug** — when calling `addTable(slide, x, y, w, data, data[0], colWidths)`, the first data row becomes a duplicate of the header row. Always pass the header array explicitly: `addTable(slide, x, y, w, data, ['Col1', 'Col2', 'Col3'], colWidths)`. Never use `data[0]` as the header argument.
- **Regex escaping in `write_file`** — when writing JavaScript files via `write_file`, backslash escaping in regex literals gets doubled (e.g. `\\d` becomes `\\\\d`). After writing, use `patch` to fix the regex to its correct unescaped form, or write the file with `patch` directly for regex-heavy code.
- **Long single-line text causes mid-word breaks** — when a long paragraph is placed in a single `addText` call with `fit: 'shrink'`, words can break mid-character across lines (e.g. "迭代升" / "级"). Use `bulletList` with separate items, or break the text into multiple `addText` calls with explicit line breaks, to prevent word fragmentation.
- **Data staleness in government PPTs** — users expect the latest policy data. Before generating, always web-search for: (a) current year's 中央一号文件, (b) new 部委规范性文件 with current-year 文号, (c) latest 自治区/市 工作要点, (d) legislative progress updates, (e) latest local news with specific data. Update the script's data values and source citations, then regenerate and re-QA.

## Verification

Before declaring done:
1. ✅ PPTX file exists and has expected slide count
2. ✅ PDF exported successfully
3. ✅ At least 3-4 key slides visually inspected (cover, data-dense, table, closing)
4. ✅ All identified issues fixed and re-verified
5. ✅ No text overflow or overlap on inspected slides
6. ✅ All images are real (no AI-generated) when required

## Support Files

- `references/doc-file-reading.md` — Detailed techniques for reading legacy `.doc` files (antiword, olefile, struct extraction)
- `references/windows-pdf-conversion.md` — comtypes + PowerPoint COM setup and troubleshooting
- `references/government-ppt-writing-style.md` — Banned vs correct language patterns, policy document full titles, and register rules for government/official PPT content
- `templates/generate_ppt_template.js` — Proven pptxgenjs script structure with reusable helpers