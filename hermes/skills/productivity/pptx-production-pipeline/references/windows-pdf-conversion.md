# Windows PPTX→PDF Conversion

## The Problem

The bundled `powerpoint` skill recommends LibreOffice (`soffice`) for PPTX→PDF conversion. On Windows, LibreOffice is often not installed, but Microsoft PowerPoint is. Use COM automation instead.

## Method: comtypes + PowerPoint COM

```python
import comtypes.client
import os

pptx_path = os.path.abspath('output/deck.pptx')
pdf_path = os.path.abspath('output/deck.pdf')

powerpoint = comtypes.client.CreateObject('Powerpoint.Application')
powerpoint.Visible = 1
deck = powerpoint.Presentations.Open(pptx_path)
deck.SaveAs(pdf_path, 32)  # 32 = ppSaveAsPDF
deck.Close()
powerpoint.Quit()
print(f'PDF saved: {pdf_path}')
```

## Prerequisites

```bash
pip install comtypes
```

Microsoft PowerPoint must be installed (Office 2016/2019/2021/365).

## SaveAs format constants

| Constant | Value | Format |
|----------|-------|--------|
| ppSaveAsPDF | 32 | PDF |
| ppSaveAsPNG | 18 | PNG images |
| ppSaveAsJPG | 17 | JPEG images |

## Troubleshooting

### "Call was rejected by callee"
PowerPoint COM can be flaky on first call. Add a retry:
```python
import time
for attempt in range(3):
    try:
        powerpoint = comtypes.client.CreateObject('Powerpoint.Application')
        break
    except:
        time.sleep(2)
```

### Path must be absolute
`Presentations.Open` requires absolute paths. Always use `os.path.abspath()`.

### Visible = 1 is required
Setting `Visible = 1` is needed for COM automation to work properly on some Office versions.

### PowerPoint process lingers
If `powerpoint.Quit()` doesn't clean up, force kill:
```python
import subprocess
subprocess.run(['taskkill', '/F', '/IM', 'POWERPNT.EXE'], capture_output=True)
```

## Alternative: LibreOffice (if installed)

```bash
"C:\Program Files\LibreOffice\program\soffice.exe" --headless --convert-to pdf --outdir output/ output/deck.pptx
```

Check if installed:
```bash
ls "C:/Program Files/LibreOffice/program/soffice.exe" 2>/dev/null
ls "C:/Program Files (x86)/LibreOffice/program/soffice.exe" 2>/dev/null
```