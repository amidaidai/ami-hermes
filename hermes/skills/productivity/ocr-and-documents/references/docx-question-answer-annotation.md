# DOCX Question Bank Answer Annotation

Use this reference when a user asks to mark answers directly after questions in a Word question bank, especially when the same document contains a later “参考答案及专家精析” section.

## Durable Workflow

1. Treat the document’s own answer section as authoritative before searching or guessing.
2. Inspect the `.docx` as a ZIP and parse `word/document.xml` when `python-docx` is missing or insufficient.
3. For Word files with columns, pagination, text boxes, or OCR-like layout, do not assume XML paragraph order equals visual reading order.
4. Try multiple extraction surfaces:
   - `python-docx` if installed.
   - Raw `word/document.xml` via safe XML parsing for in-place edits.
   - Word COM automation on Windows (`win32com.client`) to `SaveAs2(..., FileFormat=7)` for a visual-order text export when available.
   - Avoid relying on `docx2txt` without checking output length/content; some builds only emit short metadata or fail silently.
5. Build answer mappings conservatively. Prefer section/type/question-number alignment or dynamic sequence alignment over naive global zip when answer sections are split by chapter/type.
6. If the reference-answer area is reordered or missing visible leading/trailing answers, do not force uncertain matches into the document. Mark only reliable pairs and emit a skipped/unmatched report.
7. Modify the DOCX by appending a run like `（A）` to the question paragraph, preserving the last run’s style where possible.
8. Verify both ZIP integrity and Word-level openability:
   - ZIP contains `word/document.xml`.
   - Count inserted markers.
   - On Windows with Word installed, open the output via COM and print paragraph/word counts.

## Pitfalls

- A table of contents may contain “第二部分 参考答案及专家精析”; do not use the first occurrence as the real answer split. Use the real answer heading near the back half of the document.
- Word columns/pagination can interleave sections in XML; simple paragraph order may skip the first page of answers or jump across chapters.
- Duplicate bare answer paragraphs like `1.E` can be layout artifacts; skip immediate duplicates when extracting answers.
- Producing a partial but clearly verified document plus an unmatched report is better than silently mislabeling answers.

## Output Convention

Return the annotated DOCX path and, when any questions were skipped, a separate `.txt` or `.md` unmatched report explaining why. On Windows, use Markdown links with absolute `C:/...` paths wrapped in angle brackets.
