import { readFileSync } from 'node:fs';
import { evaluateAsync } from 'file:///D:/Hermes%20agent/tools/tradingview-mcp/src/connection.js';

const files = process.argv.slice(2);
if (files.length === 0) {
  console.error('Usage: node tv_pine_check_files.mjs <file1> [file2 ...]');
  process.exit(2);
}

for (const file of files) {
  const source = readFileSync(file, 'utf8');
  const js = `
    (async function() {
      const form = new URLSearchParams();
      form.append('source', ${JSON.stringify(source)});
      const response = await fetch(
        'https://pine-facade.tradingview.com/pine-facade/translate_light?user_name=Guest&pine_id=00000000-0000-0000-0000-000000000000',
        {
          method: 'POST',
          headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Referer': 'https://www.tradingview.com/'
          },
          credentials: 'include',
          body: form
        }
      );
      const text = await response.text();
      let data = null;
      try { data = JSON.parse(text); } catch (e) {}
      const inner = data && data.result ? data.result : null;
      const compactDiag = (x) => x ? {
        line: x.start && x.start.line,
        column: x.start && x.start.column,
        end_line: x.end && x.end.line,
        end_column: x.end && x.end.column,
        message: x.message
      } : x;
      return {
        ok: response.ok,
        status: response.status,
        errors: inner && inner.errors2 ? inner.errors2.map(compactDiag) : [],
        warnings: inner && inner.warnings2 ? inner.warnings2.map(compactDiag) : [],
        top_error: data && data.error ? data.error : null,
        raw_prefix: data ? null : text.slice(0, 500)
      };
    })()
  `;
  try {
    const out = await evaluateAsync(js);
    console.log(JSON.stringify({ file, chars: source.length, ...out }));
  } catch (e) {
    console.log(JSON.stringify({ file, chars: source.length, exception: e.message }));
  }
}
process.exit(0);
