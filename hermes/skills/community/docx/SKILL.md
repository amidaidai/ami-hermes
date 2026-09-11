---
name: docx
description: Create, read, edit Word documents (.docx) with formatting, tables, images, headers, and footers using python-docx. Use when user asks to create, modify, read, or convert Word documents, .docx files, or reports in Word format.
---

# DOCX Document Processor

Create, read, and edit Word documents (.docx) with proper formatting.

## Prerequisites
```bash
pip install python-docx
```

## Creating Documents

### Basic Document
```python
from docx import Document
doc = Document()
doc.add_heading('Title', level=0)
doc.add_paragraph('Some text')
doc.save('output.docx')
```

### Formatting
```python
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

p = doc.add_paragraph()
run = p.add_run('Bold and colored text')
run.bold = True
run.font.size = Pt(14)
run.font.color.rgb = RGBColor(0xFF, 0x00, 0x00)
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
```

### Tables
```python
table = doc.add_table(rows=3, cols=4, style='Table Grid')
table.cell(0, 0).text = 'Header 1'
for row in table.rows:
    for cell in row.cells:
        cell.text = 'data'
```

### Headers and Footers
```python
section = doc.sections[0]
header = section.header
header.paragraphs[0].text = 'Company Confidential'
```

### Images
```python
doc.add_picture('chart.png', width=Inches(5.0))
```

## Reading Documents

```python
doc = Document('input.docx')
for para in doc.paragraphs:
    print(para.text)
for table in doc.tables:
    for row in table.rows:
        for cell in row.cells:
            print(cell.text)
```

## Common Operations

| Task | Approach |
|------|----------|
| Create from template | `Document('template.docx')`, modify, save as new |
| Add page break | `doc.add_page_break()` |
| Change margins | `section.top_margin = Inches(1)` |
| Add bullet list | `doc.add_paragraph('item', style='List Bullet')` |
| Merge cells | `cell.merge(cell)` |

## Output

Always verify the generated .docx file opens correctly before declaring completion.
