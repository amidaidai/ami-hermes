// 编辑器缓冲直读（只读）——确认「点保存将落什么版本」。
// 与云读回（tv_cloud_readback.mjs）配对：一个答「云端现在是什么」，一个答「保存后会变成什么」。
//
// 跑法（TV Desktop 已开、CDP 9222 在）：
//   1) 先打开 Pine 编辑器面板（Monaco 未挂载时 finder 找不到）：
//      MCP ui_open_panel {"panel":"pine-editor","action":"open"}
//   2) cd 'D:/Hermes agent' && node <本文件> [outFile] [candidateFile]
//   3) 关面板收尾（MCP close）
//
// 注意：不要用 MCP pine_get_source 读大脚本——它把全量源码返回进上下文（200KB+）。
// 本脚本源码写盘、只打印长度/sha 摘要；判据：getValue() 为 LF 归一文本，与候选文件的
// LF 归一等值即逐字一致（norm = CRLF→LF + trimEnd）。
import {pathToFileURL} from 'node:url';
import fs from 'node:fs';
import crypto from 'node:crypto';

const REPO = (process.env.TANGXI_REPO || 'D:/Hermes agent').replace(/\\/g, '/').replace(/\/+$/, '');
let evaluateAsync;
try {
  ({evaluateAsync} = await import(pathToFileURL(REPO + '/tools/tradingview-mcp/src/connection.js').href));
} catch (e) {
  console.error('无法加载 connection.js：' + e.message + '（检查 TANGXI_REPO 或仓库路径：' + REPO + '）');
  process.exit(1);
}

const outFile = process.argv[2] || 'editor_buffer_read.pine';
const candPath = process.argv[3] || null;
const norm = s => s.replace(/\r\n/g, '\n').trimEnd();
const sha = s => crypto.createHash('sha256').update(s).digest('hex');

// Monaco 定位：页面上下文没有 window.monaco 全局，必须走 React fiber 遍历。
// 片段与 tools/tradingview-mcp/src/core/pine.js 的 FIND_MONACO 一致。
const FIND_MONACO = `
  (function findMonacoEditor() {
    var containers = document.querySelectorAll('.monaco-editor.pine-editor-monaco');
    if (!containers || containers.length === 0) return null;
    for (var c = 0; c < containers.length; c++) {
      var el = containers[c];
      var fiberKey;
      for (var i = 0; i < 20; i++) {
        if (!el) break;
        fiberKey = Object.keys(el).find(function(k) { return k.startsWith('__reactFiber$'); });
        if (fiberKey) break;
        el = el.parentElement;
      }
      if (!fiberKey) continue;
      var current = el[fiberKey];
      for (var d = 0; d < 15; d++) {
        if (!current) break;
        if (current.memoizedProps && current.memoizedProps.value && current.memoizedProps.value.monacoEnv) {
          var env = current.memoizedProps.value.monacoEnv;
          if (env.editor && typeof env.editor.getEditors === 'function') {
            var editors = env.editor.getEditors();
            var best = null;
            var bestScore = -1;
            for (var e = 0; e < editors.length; e++) {
              var editor = editors[e];
              var node = editor && typeof editor.getDomNode === 'function' ? editor.getDomNode() : null;
              var rect = node && typeof node.getBoundingClientRect === 'function' ? node.getBoundingClientRect() : null;
              var visible = !!(node && node.isConnected !== false && rect && rect.width > 0 && rect.height > 0);
              var focused = !!(visible && document.activeElement && typeof node.contains === 'function' && node.contains(document.activeElement));
              var area = visible ? rect.width * rect.height : 0;
              var score = (focused ? 1000000000000 : 0) + (visible ? 1000000000 : 0) + area;
              if (score > bestScore) { best = editor; bestScore = score; }
            }
            if (best) return { editor: best, env: env };
          }
        }
        current = current.return;
      }
    }
    return null;
  })()
`;

const src = await evaluateAsync(`(async()=>{
  var m = ${FIND_MONACO};
  if (!m) return null;
  try { return m.editor.getValue(); } catch(e) { return 'ERR:'+String(e); }
})()`);

if (src === null || src === undefined) {
  console.log('FIND_MONACO: null —— 编辑器面板未开或 Monaco 未挂载；先用 MCP ui_open_panel {"panel":"pine-editor","action":"open"} 打开再跑。');
  process.exit(2);
}
if (typeof src === 'string' && src.startsWith('ERR:')) { console.log(src); process.exit(2); }

fs.writeFileSync(outFile, src, 'utf8');
const out = {
  outFile,
  editor_len: src.length,
  editor_lines: src.split('\n').length,
  editor_sha24: sha(src).slice(0, 24),
};
if (candPath) {
  const cand = fs.readFileSync(candPath, 'utf8');
  out.candidate = candPath;
  out.match_candidate_norm = norm(src) === norm(cand);
}
console.log(JSON.stringify(out, null, 1));
process.exit(0);
