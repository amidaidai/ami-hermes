# Windows PPTX QA Pipeline

## Prerequisites

```bash
pip install pymupdf comtypes
npm install pptxgenjs sharp
```

PowerPoint must be installed (COM automation uses the desktop app).

## Step 1: Generate PPTX

```bash
cd "C:/Users/Administrator/Desktop/project_dir" && node generate_ppt.js
```

## Step 2: Convert PPTX to PDF (PowerPoint COM)

```python
import comtypes.client, os

pptx_path = os.path.abspath('output/presentation.pptx')
pdf_path = os.path.abspath('output/presentation_qa.pdf')

powerpoint = comtypes.client.CreateObject('Powerpoint.Application')
powerpoint.Visible = 1
deck = powerpoint.Presentations.Open(pptx_path)
deck.SaveAs(pdf_path, 32)  # 32 = ppSaveAsPDF
deck.Close()
powerpoint.Quit()
print(f'PDF saved: {os.path.getsize(pdf_path)/1024:.0f} KB')
```

LibreOffice (soffice) is NOT available on this Windows host. Use PowerPoint COM via comtypes instead. Do NOT try `soffice --headless --convert-to pdf` — it will fail.

## Step 3: Convert PDF pages to images (PyMuPDF)

```python
import fitz, os

doc = fitz.open('output/presentation_qa.pdf')
qa_dir = 'assets/qa'
os.makedirs(qa_dir, exist_ok=True)
for i, page in enumerate(doc, 1):
    pix = page.get_pixmap(dpi=130)
    pix.save(os.path.join(qa_dir, f'slide-{i:02d}.jpg'))
doc.close()
```

pdf2image requires poppler which is NOT installed. Use PyMuPDF (fitz) directly instead.

## Step 4: Visual QA with vision_analyze

Call vision_analyze on key slides:
- Slide 1 (cover): check title readability, image quality
- Slide 2 (TOC): check all section titles visible, no overflow
- Data-heavy slides: check metrics visible, progress bars correct
- Text-heavy slides (policy, tables): check overflow, alignment
- Closing slide: check contrast of text over background photo

Common issues to look for:
- Text overflow in boxes (reduce fontSize or shorten text)
- Low contrast: semi-transparent bars over bright photos (set transparency=0)
- Long policy titles: use fontSize: 19 in addTitle opts
- Gray secondary text on white-over-photo: use color: '3A3A3A', bold: true

## Step 5: Fix and regenerate

Patch the JS script, then repeat steps 1-4 for affected slides only.

## Reading .doc files (old binary Word format)

markitdown and mammoth CANNOT read .doc (only .docx). Options:

### antiword (for standard .doc)
```bash
antiword "path/to/file.doc"
```
Available at /mingw64/bin/antiword on this host.

### olefile + struct (for WPS-generated .doc that antiword rejects)
```python
import olefile, struct, re

fname = 'path/to/file.doc'
ole = olefile.OleFileIO(fname)
wd = ole.openstream('WordDocument').read()
fc_min = struct.unpack_from('<I', wd, 0x18)[0]
fc_mac = struct.unpack_from('<I', wd, 0x1C)[0]
text_bytes = wd[fc_min:fc_mac]
text = text_bytes.decode('utf-16-le', errors='ignore')
readable = re.findall(r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef\w\s.,;:!?()【】《》、。；：！？（）\-\—\%\"\'/]+', text)
result = ''.join(readable)
print(result[:5000])
ole.close()
```

### .docx files (modern format)
markitdown works for .docx. mammoth also works for .docx → markdown conversion.