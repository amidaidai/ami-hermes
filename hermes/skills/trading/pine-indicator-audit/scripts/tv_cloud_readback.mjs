// 云读回（只读）——TradingView 云端已保存的 Pine 源码 vs 本地候选文件。
// 用途：识别/复核「图表跑新码、云端仍旧码」的保存缺口；保存后做三方一致核验（上传=仓库=云端）。
//
// 跑法（TV Desktop 已开、CDP 9222 在）：cd 'D:/Hermes agent' && node <本文件> [outDir]
// 换版：更新 CANDIDATES（候选文件路径）与 SVP 的 MARKERS（关键特征串，
//       用于「本地未同步但修复已入云」的定向判断——例：拆位修复的特征串在云源码里出现即修复已保存）。
// 输出：<outDir>/<name>_cloud_readback.pine 与 cloud_compare.json；stdout 打印摘要。
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

const outDir = (process.argv[2] || REPO + '/outputs').replace(/\\/g, '/').replace(/\/+$/, '');
fs.mkdirSync(outDir, {recursive: true});
const norm = s => s.replace(/\r\n/g, '\n').trimEnd();
const sha = s => crypto.createHash('sha256').update(s).digest('hex');

const CANDIDATES = [
  {
    name: 'SVP', id: 'USER;45827730112b45fab9c436dea8436ad8',
    candidate: REPO + '/outputs/pine_20260905/SVP_audit_fixed18_20260916.pine',
    markers: {
      'bit2048': 'cvdLowSample ? 2048 : 0',
      'bit128': 'cvdLowSample ? 128 : 0',
      'qualify_guard': 'not cvdQualityOk and not cvdLowSample',
    },
  },
  {
    name: 'AggVol', id: 'USER;60e1093c30124b7daead43f444f250f0',
    candidate: REPO + '/outputs/pine_20260905/AggVol_audit_fixed14_20260910.pine',
    markers: {},
  },
];

// 1) saved 列表（查重复标题/身份漂移）
const list = await evaluateAsync(`(async()=>{const l=await (await fetch('https://pine-facade.tradingview.com/pine-facade/list/?filter=saved',{credentials:'include'})).json();return l.map(x=>({id:x.scriptIdPart,name:x.scriptName,ver:x.version,mod:x.modified}));})()`);
console.log('saved scripts total:', list.length);
for (const x of list) {
  if (/SVP|Aggregated/i.test(x.name || '')) {
    console.log(' *', x.id, '|', x.name, '| v' + x.ver, '| mod', new Date(x.mod * 1000).toISOString());
  }
}

// 2) 逐目标读回 + 对比
const out = [];
for (const t of CANDIDATES) {
  const data = await evaluateAsync(`(async()=>{const l=await (await fetch('https://pine-facade.tradingview.com/pine-facade/list/?filter=saved',{credentials:'include'})).json();const s=l.find(x=>x.scriptIdPart===${JSON.stringify(t.id)});if(!s)throw Error('Missing exact ID');const d=await(await fetch('https://pine-facade.tradingview.com/pine-facade/get/'+s.scriptIdPart+'/'+s.version,{credentials:'include'})).json();return {version:s.version,name:s.scriptName,modified:s.modified,source:d.source};})()`);
  fs.writeFileSync(`${outDir}/${t.name}_cloud_readback.pine`, data.source, 'utf8');
  const cand = fs.readFileSync(t.candidate, 'utf8');
  const r = {
    name: t.name,
    cloud_version: data.version,
    cloud_modified_iso: new Date(data.modified * 1000).toISOString(),
    cloud_sha24: sha(data.source).slice(0, 24),
    cloud_lines: data.source.split('\n').length,
    candidate_file: t.candidate.split('/').pop(),
    candidate_sha24: sha(cand).slice(0, 24),
    candidate_match: norm(data.source) === norm(cand),
  };
  const markers = {};
  for (const [k, v] of Object.entries(t.markers)) markers[k] = data.source.includes(v);
  if (Object.keys(markers).length) r.markers = markers;
  out.push(r);
  console.log(JSON.stringify(r));
}
fs.writeFileSync(`${outDir}/cloud_compare.json`, JSON.stringify(out, null, 2), 'utf8');
process.exit(0);
