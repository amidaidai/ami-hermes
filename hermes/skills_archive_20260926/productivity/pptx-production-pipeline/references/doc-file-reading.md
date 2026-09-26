# Reading Legacy `.doc` Files on Windows

## The Problem

`markitdown` only supports `.docx` (Office Open XML). Legacy `.doc` files (OLE/Compound Binary Format) fail with `UnsupportedFormatException`. On Windows, you often receive `.doc` files from government/enterprise users.

## Tool Comparison

| Tool | Works? | Notes |
|------|--------|-------|
| `markitdown` | ❌ | Only `.docx` |
| `mammoth` | ❌ | Only `.docx` (raises "Could not find the body element") |
| `antiword` | ✅ for standard Word docs | Available at `/mingw64/bin/antiword` in git-bash. Clean text output. |
| `antiword` on WPS docs | ❌ | WPS-created `.doc` files have different internal structure. Error: "not a Word Document" |
| `olefile + struct` | ✅ (universal fallback) | Reads OLE compound binary directly, extracts UTF-16LE text from WordDocument stream |

## Method 1: antiword (try first)

```bash
antiword "file.doc"
```

- Fast, clean output with table formatting
- Available in MSYS2/git-bash at `/mingw64/bin/antiword`
- Fails on WPS-created `.doc` files with "not a Word Document"

## Method 2: olefile + struct (fallback)

When antiword fails, extract text directly from the OLE binary:

```python
import olefile, struct, re

ole = olefile.OleFileIO('file.doc')

# List available streams (for debugging)
print('Streams:', ole.listdir())

# Read WordDocument stream
wd = ole.openstream('WordDocument').read()

# FIB: get text boundaries
# fcMin at offset 0x18, fcMac at offset 0x1C (32-bit little-endian)
fc_min = struct.unpack_from('<I', wd, 0x18)[0]
fc_mac = struct.unpack_from('<I', wd, 0x1C)[0]

# Check if complex format (piece table)
flags = struct.unpack_from('<H', wd, 0xA)[0]
is_complex = (flags & 0x0004) != 0

# Extract text bytes
text_bytes = wd[fc_min:fc_mac]

# Decode as UTF-16LE (standard for modern .doc files with Chinese)
text = text_bytes.decode('utf-16-le', errors='ignore')

# Filter readable characters (Chinese + ASCII punctuation)
readable = re.findall(
    r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef\w\s.,;:!?()【】《》、。；：！？（）\-\—\%\"\'/]+',
    text
)
result = ''.join(readable)
print(result[:6000])
```

### How it works

- `.doc` files are OLE (Object Linking and Embedding) compound binary files
- The `WordDocument` stream contains the document text
- The FIB (File Information Block) at the start of the stream has `fcMin` (text start) and `fcMac` (text end) offsets
- Text is stored as UTF-16LE in documents with Chinese characters
- The `0Table` or `1Table` stream contains formatting and piece table info (not needed for text extraction)

### Stream names vary

Different Word versions use different table stream names:
- `1Table` (standard Word 97-2003)
- `0Table` (WPS and some variants)
- Check `ole.listdir()` to find the right one

### When text extraction gives garbled output

If UTF-16LE produces garbled text, try GBK/CP936:
```python
text_gbk = text_bytes.decode('gbk', errors='ignore')
```

## Method 3: LibreOffice (if installed)

```bash
soffice --headless --convert-to txt "file.doc"
```

Only works if LibreOffice is installed. On Windows, it's usually at:
- `C:\Program Files\LibreOffice\program\soffice.exe`
- `C:\Program Files (x86)\LibreOffice\program\soffice.exe`

## Prerequisites

```bash
pip install olefile  # for Method 2
# antiword is pre-installed in MSYS2/git-bash
```