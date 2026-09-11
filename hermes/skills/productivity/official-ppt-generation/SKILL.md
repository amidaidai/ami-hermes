---
name: official-ppt-generation
description: "Generate professional government/official training PPTs using pptxgenjs on Windows — writing style rules, QA pipeline, and common pitfalls."
---

# Official PPT Generation

Create professional Chinese government/official training presentations using pptxgenjs, with proper bureaucratic writing style and visual QA.

## When to use

- User asks for a government training PPT (培训PPT)
- User provides official data and policy documents to turn into slides
- User wants a presentation that looks like it was made by a government office, not by AI

## Writing style rules (CRITICAL)

Government/official PPTs must use formal bureaucratic language (公文语态). The user strongly rejected AI-style writing. These rules are non-negotiable:

### Banned patterns
- **造词/咨询风术语**: "作战图""安全垫""五重压力叠加期""一图两表一台账""三优先""红黄绿管理""周循环""系统战""攻坚""硬约束" — never invent catchy names for concepts
- **口语化标题**: "底数要清""先把四件事做起来""不是任务重三个字可以概括" — use noun phrases or formal descriptors instead
- **"不是…而是…"句式**: rewrite as direct statements
- **感叹号**: never use in government PPTs
- **"不能…""严禁…"口语化**: use "须""不得" in formal register
- **断言式/口号式收尾**: "守住的不是一个数字" → "博白县粮食安全的根基"

### Correct patterns
- **标题**: Use formal noun phrases: "耕地保护基本情况""政策法规变化与面临形势""年度重点工作安排""存在的主要困难"
- **政策文件**: Always use full official title and document number: 《自然资源部 农业农村部关于改革完善耕地占补平衡管理的通知》（自然资发〔2024〕204号）
- **正文**: Declarative sentences, no exclamation marks, no rhetorical questions
- **数据标注**: "截至6月12日""以正式台账为准""以正式通报为准"
- **备注**: Concise lecturer notes, professional tone

### Title transformation examples
| Bad (AI-style) | Good (Government) |
|---|---|
| 今天要形成四个共识 | 培训内容 |
| 守线结果：有余量，但不能把余量当作可占空间 | 2025年度耕地保护目标完成情况 |
| 六个变化：镇村工作的判断标准已经变了 | 当前耕地保护政策主要变化 |
| 形势判断：博白正处在"五重压力叠加期" | 当前面临的主要形势 |
| 年度作战图：三项攻坚、两个支撑、一个闭环 | 年度重点工作总体安排 |
| 培训后，先把四件事做起来 | 下一步工作要求 |

## Workflow

### 1. Setup and asset preparation
- Install deps: `npm install pptxgenjs sharp` in project directory
- Place all images in `assets/` directory — **never use AI-generated photos**, only real local photos from government websites, news outlets, or official sources
- Use `sharp` to pre-process images (resize, crop, compress to JPEG)

### 2. Script structure
- Single `generate_ppt.js` file with all slide definitions
- Common helper functions: `addText`, `rect`, `line`, `image`, `tag`, `metric`, `callout`, `hBar`, `sectionDivider`, `bulletList`, `addFooter`, `addTitle`
- 16:9 layout: width=13.333, height=7.5 inches
- Font: `Microsoft YaHei` for Chinese
- Color palette: pick topic-appropriate colors (e.g., forest green for agriculture, not generic blue)

### 3. Generate PPTX
```bash
cd project_dir && node generate_ppt.js
```

### 4. Convert to PDF for QA (Windows only)
See [references/windows-pptx-qa.md](references/windows-pptx-qa.md) for the complete conversion and QA pipeline.

### 5. Visual QA
- Convert PDF pages to images using PyMuPDF (fitz)
- Use vision_analyze on key slides (cover, data-heavy pages, text-heavy pages, closing)
- Check for: text overflow, element overlap, contrast issues, alignment
- Fix issues by patching the JS script, then regenerate

## Pitfalls

- **DO NOT delegate PPT text rewriting to subagents.** The user was frustrated when I tried to delegate instead of doing it directly. When the user says "修改里面的东西" or "重做", do it yourself with patches, one slide at a time.
- **DO NOT use AI-generated images.** Government PPTs must use real photos from official sources. Verify image provenance and cite sources in slide footers.
- **Policy citations must use full document titles and numbers.** Don't abbreviate "2024 两办意见" — write the full title. Include publication date and effective date.
- **Data口径 (caliber) matters.** Distinguish between 考核任务数, 空间划定数, and 遥感监测数 — never mix them.
- **疑似图斑 ≠ 违法面积.** Remote sensing patches are investigation leads, not final findings.
- **.doc files (old binary format)**: markitdown and mammoth cannot read them. Use `antiword` for older Word docs, or `olefile + struct` for WPS-generated .doc files. See [references/windows-pptx-qa.md](references/windows-pptx-qa.md).
- **Long policy titles in slide headers**: use `fontSize: 19` in addTitle opts to prevent overflow when the full document title is very long.
- **Semi-transparent white bars over photos**: set transparency to 0 (fully opaque) and use dark bold text (`color: '3A3A3A'`) for secondary text to ensure readability.
- **Policy completeness — user expects ALL of these slides**:
  - 政策废止与替代关系页 (which old policies are abolished, with effective dates)
  - 部门职责分工页 (which department handles what, with legal basis article numbers)
  - 上级规划依据页 (province → city → county task decomposition with full规划 names)
  - 八不准 or equivalent regulatory prohibitions spelled out
  - 立法进展 (draft laws and their审议 status)
  - 本地案例页 (concrete village/town examples from official news)
- **Source page layout for 20+ entries**: use 11/11 column split at 8.5pt font, 0.51" row spacing, URL text at 6.2pt. Adjust split threshold when adding entries.

## Search and verify policy information

When creating government PPTs, always search for and verify:
1. Full official document titles and document numbers (文号)
2. Effective dates and implementation dates
3. Issuing authorities (发文机关)
4. Key data points and their sources
5. Latest policy updates and amendments

Use web_search and web_extract to pull from gov.cn, mnr.gov.cn, and provincial government sites.