---
name: gov-presentation-creation
description: "Create government/official Chinese presentations (培训PPT, 工作汇报) with proper 公文语态 writing style, pptxgenjs generation, and Windows QA pipeline."
---

> **同族导航** — 演示/PPT 组 8 个技能，先按**产出物**选路，别加载错（本技能 = 入口）
> · **本技能 `gov-presentation-creation`** = 政府/官方中文演示 · 公文语态与政策核查（用户首选路线）
> · 政府/公文类：`gov-presentation-creation`（政府/官方中文演示 · 公文语态与政策核查（用户首选路线））⭐、`official-ppt-generation`（政府/官方培训 PPT 生成器 + QA）
> · 通用 PPTX 管线：`pptx-production-pipeline`（通用 PPTX 全流程（读源文档→pptxgenjs 生成→Windows 转换/QA））、`powerpoint`（python-pptx 读写编辑 .pptx（非生成管线））
> · 网页 HTML 演示：`html-ppt`（网页 PPT（多风格/动画，HTML 交付））、`guizang-ppt-skill`（横向翻页网页 PPT（单 HTML + WebGL））
> · 图像优先：`ppt-image-first`（图像优先：先定视觉方向再做页）、`gpt-image2-ppt`（图像优先：gpt-image-2 出高分辨率页再拼 PPTX）
> · 组内成员互斥度低，同时加载会互相抢触发词；改一个就同步其余。


# Government Presentation Creation

Create professional presentations for Chinese government agencies — training decks (培训PPT), work briefings (工作汇报), policy explanations (政策解读). The defining requirement is **公文语态** (official document tone), not AI-flavored language.

## When to use

- User asks for a 培训PPT, 工作汇报, 政策解读 for a government office (政府机关, 办公室, 局, 委)
- User mentions 田长制, 田长办, 耕地保护, 国土空间规划, or any government training context
- User provides official data/documents and wants a training or briefing deck
- User says "不要AI的话" / "不专业" / "像成熟的PPT" about a previously generated deck

## Writing Style — 公文语态 (CRITICAL)

This is the #1 user requirement. AI-flavored language will be rejected. When in doubt, write like a government document, not like a consultant.

| Rule | Wrong (AI style) | Right (公文语态) |
|------|------------------|------------------|
| Titles | "五重压力叠加期" "作战图" "安全垫" | "当前面临的主要形势" "年度重点工作总体安排" |
| Body sentences | "不是…而是…" "不能…" | Direct declarative statements |
| Tone | Colloquial, exclamatory | Formal, measured, no exclamation marks |
| Neologisms | "一图两表一台账" "红黄绿管理" | Use existing official terminology only |
| Section headers | "底数要清""政策要准" | "耕地保护基本情况""政策法规变化" |
| Closing | "先把四件事做起来" | "下一步工作要求" |

### Key principles

1. **Full official document names** — cite policies by full title + document number (e.g., 《中共中央办公厅 国务院办公厅关于加强耕地保护提升耕地质量完善占补平衡的意见》, 自然资发〔2024〕204号)
2. **No consulting-framework language** — avoid coined phrases like "三优先""六步闭环""系统战" unless from an actual policy document
3. **Speaker notes** — concise lecturer prompts, not analysis commentary
4. **Data precision** — preserve exact figures (84.1162万亩, not "约84万亩")
5. **Source attribution** — every data point and policy citation needs a source line in the footer
6. **Local photos only** — for jurisdiction-specific presentations, use only real local photos from official sources, never AI-generated images

## Workflow

### 0. Verify current date and data freshness (FIRST STEP)

Check today's date before writing any content. Search for the latest policies issued this year:
- Current year's中央一号文件 (issued every January/February)
- Any new部委规范性文件 with current-year文号
- Latest自治区/市工作要点 (usually issued in Q1)
- Legislative progress updates (laws pending审议)
- Latest statistical achievements published in官方媒体

If any policy from the previous year has been superseded, note the abolition/replacement relationship explicitly.

### 1. Gather information (parallel)

- Read all user-provided documents (antiword for .doc, markitdown for .docx/.pptx)
- Web search for current policies, regulations, and local news
- Check existing assets/images in the working directory
- Identify the issuing agency (培训单位) and required format

### 2. Generate PPTX with pptxgenjs

Use `pptxgenjs` (Node.js) for full programmatic control. Typical structure:

```javascript
const pptxgen = require('pptxgenjs');
const pptx = new pptxgen();
pptx.defineLayout({ name: 'WIDE', width: 13.333, height: 7.5 });
pptx.layout = 'WIDE';
// ... build slides with addText, addImage, addShape
await pptx.writeFile({ fileName: 'output.pptx' });
```

### 3. QA pipeline on Windows

When LibreOffice/Poppler are unavailable but PowerPoint is installed:

**PPTX → PDF** (via PowerPoint COM automation):
```python
import comtypes.client, os
pp = comtypes.client.CreateObject('Powerpoint.Application')
pp.Visible = 1
deck = pp.Presentations.Open(os.path.abspath('output.pptx'))
deck.SaveAs(os.path.abspath('output_qa.pdf'), 32)  # 32=ppSaveAsPDF
deck.Close()
pp.Quit()
```

**PDF → JPEG** (via PyMuPDF, no Poppler needed):
```python
import fitz, os
doc = fitz.open('output_qa.pdf')
for i, page in enumerate(doc, 1):
    pix = page.get_pixmap(dpi=130)
    pix.save(f'qa/slide-{i:02d}.jpg')
doc.close()
```

Install: `pip install comtypes pymupdf`

### 4. Visual QA

Use `vision_analyze` on key slides. Check:
- Text overflow / overlap
- Low-contrast text (especially on photo backgrounds — use solid white bars, not semi-transparent)
- All data figures visible and correct
- Source citations in footer
- Policy document names complete and accurate

### 5. Fix and re-verify

Fix issues → re-render only affected slides → re-verify. Do not declare success until one fix-and-verify cycle completes clean.

### 6. Data refresh pass (MANDATORY for government PPTs)

After the initial generation, the user will often ask to "联网更新数据" or "搜索最新政策". This is NOT optional — government PPTs must reflect the absolute latest data. Run a second round of web searches targeting:

- Latest local news for the jurisdiction (e.g., "博白县 2026 耕地保护 田长制 最新")
- Latest provincial work priorities (e.g., "广西 2026 田长制 工作要点")
- Latest national data announcements (e.g., "全国耕地面积 2026 最新")
- Legislative progress updates (e.g., "耕地保护和质量提升法 草案 2026 审议")
- Any new ministerial notices with current-year 文号

Then patch the generation script with updated data values, source citations, and policy list entries. Regenerate, re-render, and re-QA the affected slides. This session's data refresh added: 18.65亿亩/15.46亿亩 national targets, 龙潭镇3.3万亩 grid management details, 数智耕保 platform + 田长巡 APP, 国发〔2026〕14号 十五五规划, and 农建发〔2025〕3号 高标准农田质量管理办法.

## Pitfalls

- **CURRENT DATE CHECK (FIRST STEP):** Before writing any content, check today's date. If the session is in 2026, ALL policy citations, data figures, and regulatory references must reflect 2026-era documents. Do NOT default to last year's policies. The user was deeply frustrated when I used 2025 data throughout a PPT generated in July 2026. Search for the latest version of every policy before citing it. Specifically verify: (a) Is there a new central一号文件 this year? (b) Has any pending legislation been passed? (c) Are there new部门规范性文件 with current-year文号? (d) Has the自治区/市 issued new工作要点 this year?
- **DO NOT delegate PPT text rewriting to subagents.** The user was frustrated when I tried to delegate instead of doing it directly. When the user says "修改里面的东西" or "重做", do it yourself with patches, one slide at a time. The user wants to see you working, not handing off. Subagents are useful for parallel research or data extraction, but NOT for content writing or text rewriting — the user was explicitly frustrated when I tried to delegate text work to a subagent.
- **Content-completeness gap: Training PPTs for government agencies must include a "Training Summary / Q&A" page (培训小结).** A dedicated summary slide before the closing actions is expected for face-to-face training sessions — it gives the主持人 a natural transition to Q&A and confirms key takeaways. A 40-page government training deck without a summary/Q&A page looks incomplete.
- **AI language creep**: Even after knowing the rules, pptxgenjs code tends to embed catchy titles. Review every text string against the 公文语态 rules before generating.
- **Semi-transparent white bars on photo slides**: Gray secondary text becomes unreadable. Use solid white (transparency=0) and dark text color (e.g., '3A3A3A') with bold.
- **Source page overflow**: When adding many policy references, reduce font size and row height rather than letting text overflow. 22+ entries fit in 2 columns (11/11 split) at 8.5pt with 0.51" row spacing; URL text at 6.2pt. For 25+ entries, use 13/13 split at 7.5pt with 0.43" row spacing; URL text at 5.5pt. Adjust column split threshold when entries increase.
- **Timeline page with 11+ nodes**: The default `x = 0.37 + i * 1.41` spacing only fits 9 nodes. For 11 nodes, change to `x = 0.22 + i * 1.23` to prevent the last node from being cut off at the right edge.
- **Adding rows to an existing layout**: When inserting a new row into a fixed-height layout (e.g., adding 十五五规划 row to a 3-row superior-plan slide), reduce per-row height proportionally (e.g., from 1.3" to 1.0") and adjust the y-offset formula. Do NOT just append at the bottom — the footer bar will overlap.
- **markitdown cannot read .doc (OLE) files**: Use `antiword` for old .doc format, or `olefile` + manual extraction for WPS-generated .doc files.
- **Policy时效**: Always web-search to verify policy is current before citing. Note expiration dates and abolition/replacement relationships. Include effective dates and abolition dates in every citation.
- **Visual style must be austere, not decorative** — Government training PPTs are rejected if they look "花里胡哨" (too flashy). When the user complains about visual noise, strip all decorative elements: remove colored vertical bars, gold separators, rounded-corner tags, progress bars, semi-transparent overlays, and gradient backgrounds. Switch to a clean white background with dark-blue (藏蓝 #1a365d) headings, black body text (#333333), and standard alternating-row tables (dark-blue header + white/light-gray rows). Photos should appear **only** on cover and section-divider slides; never overlay text on photos.
- **Content density over page count** — Users reject 40-page decks where each page is visually busy but information-light. Instead, consolidate into ~25 pages using standard tables and bullet lists: one topic per slide, all data in a single table, no scattered colored metric boxes. The same total content fits in fewer pages with higher information density per page.
- **Long policy titles in slide headers**: use `fontSize: 19` in addTitle opts to prevent overflow when the full document title is very long.
- **User expects depth and density**: "内容扎实详细一些" and "材料齐全" mean the user wants comprehensive content — not minimalist slides. Include all relevant policies, data breakdowns, department responsibilities, abolition/replacement relationships, local case studies with specific numbers, and legislative progress. A 40-page deck is appropriate for a full-day training.
- **addTable header/data separation**: The `addTable(slide, x, y, w, data, header, colWidths)` helper takes `data` (body rows) and `header` (column headers) as separate parameters. Never pass `data[0]` as the `header` argument — this creates a duplicate header row when the first data row happens to match the intended headers. Always pass an explicit header array: `addTable(slide, x, y, w, data, ['列1', '列2', '列3'], colWidths)`. This bug was caught in visual QA on a 永农禁止事项 slide where the first data row repeated the column headers verbatim.
- **Reuse existing scripts when available**: Before building a government PPT from scratch, check the working directory for existing `src/generate_ppt*.js` scripts, `assets/prepared/` directories, and `package.json` with pptxgenjs dependencies. If a prior session produced a working script, extend it with patches rather than rebuilding. This session extended a 30-slide script to 43 slides by adding new slide blocks to the second section (政策变化), reusing all helper functions, color palette, and image assets.

## Content completeness checklist

When the user asks for a "专业的" government PPT, they expect ALL of the following:

1. **Policy废止与替代关系** — explicitly show which old policies are abolished/replaced, with effective dates (e.g., "2025年1月1日起不再受理原管理方式占补平衡"). Users want to see the policy transition timeline, not just current rules.
2. **部门职责分工** — a dedicated slide showing which department (自然资源、农业农村、林草、党委政府) handles what, with legal basis (article numbers from the relevant法规).
3. **上级规划依据** — show the hierarchical task decomposition from province → city → county, with each level's规划 full name and文号.
4. **Policy full names with dates** — every policy citation must include: full title, document number (文号), and publication/effective date. Never abbreviate.
5. **Local case studies** — concrete examples with village/town names, project areas, and infrastructure details from official news sources.
6. **"八不准" or equivalent regulatory requirements** — spell out the specific prohibitions, not just reference the document.
7. **Legislation in progress** — note draft laws and their审议 status (e.g., 耕地保护和质量提升法草案: 2025年10月一审, 2026年4月二审, 尚未通过).

## Reference files

- `references/耕地保护政策文件清单.md` — Complete list of 耕地保护 policies (2020-2025) with full names, document numbers, and key provisions. Reusable for any land-protection presentation.

## Overlap with other skills

- `powerpoint` (bundled) — general PPTX creation/editing; this skill specializes in government/Chinese official context
- `ppt-image-first` (community) — visual-first approach; not suited for data-heavy government decks where content drives design