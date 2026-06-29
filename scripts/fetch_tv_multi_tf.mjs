/**
 * Fetch TradingView data across multiple timeframes via CDP.
 * Usage: node fetch_tv_multi_tf.mjs [symbol]
 */
import CDP from 'chrome-remote-interface';
import fs from 'fs';
import path from 'path';

const TARGET_SYMBOL = process.argv[2] || 'BINANCE:BTCUSDT.P';
const TIMEFRAMES = ['15', '60', '240'];
const OUTPUT_BASE = 'C:/Users/Administrator/AppData/Local/hermes/data';
const ticker = TARGET_SYMBOL.split(':').pop() || TARGET_SYMBOL;

function safeString(str) {
  return JSON.stringify(String(str));
}

async function evaluate(client, expression) {
  const result = await client.Runtime.evaluate({
    expression,
    returnByValue: true,
    awaitPromise: true,
  });
  if (result.exceptionDetails) {
    throw new Error('Eval error: ' + (result.exceptionDetails.text || JSON.stringify(result.exceptionDetails)));
  }
  return result.result.value;
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

function parseTVValue(raw) {
  if (raw == null || raw === '' || raw === '∅' || raw === '\\u2205') return null;
  const str = String(raw)
    .replace(/,/g, '')
    .replace(/−/g, '-')
    .replace(/\\u2212/g, '-')
    .trim();
  const num = parseFloat(str);
  return isNaN(num) ? null : num;
}

async function fetchTF(client, resolution) {
  console.log(`\n=== Fetching ${resolution} ===`);
  
  // Set timeframe
  await evaluate(client, `
    (function() {
      var chart = window.TradingViewApi._activeChartWidgetWV.value();
      chart.setResolution(${safeString(resolution)}, {});
    })()
  `);
  await sleep(3000);

  // Get chart state
  const state = JSON.parse(await evaluate(client, `
    (function() {
      var chart = window.TradingViewApi._activeChartWidgetWV.value();
      return JSON.stringify({
        symbol: chart.symbol(),
        resolution: chart.resolution(),
      });
    })()
  `));
  console.log('Chart state:', state);

  // Get study values
  let studies = JSON.parse(await evaluate(client, `
    (function() {
      var chart = window.TradingViewApi._activeChartWidgetWV.value()._chartWidget;
      var model = chart.model();
      var sources = model.model().dataSources();
      var results = [];
      for (var si = 0; si < sources.length; si++) {
        var s = sources[si];
        if (!s.metaInfo) continue;
        try {
          var meta = s.metaInfo();
          var name = meta.description || meta.shortDescription || '';
          if (!name) continue;
          var values = {};
          try {
            var dwv = s.dataWindowView();
            if (dwv) {
              var items = dwv.items();
              if (items) {
                for (var i = 0; i < items.length; i++) {
                  var item = items[i];
                  if (item._value && item._value !== '\\u2205' && item._title) values[item._title] = item._value;
                }
              }
            }
          } catch(e) {}
          if (Object.keys(values).length > 0) results.push({ name: name, values: values });
        } catch(e) {}
      }
      return JSON.stringify(results);
    })()
  `));
  studies = JSON.parse(studies);
  console.log('Found', studies.length, 'studies');

  let vwap = null, band1_high = null, band1_low = null, band2_high = null, band2_low = null;
  let w_vwap = null, m_vwap = null;
  let ema9 = null, ema21 = null, ema34 = null, ema55 = null;
  let cvd = null, cvd_slope = null;
  let poc = null, vah = null, valPrice = null, dopen = null;

  const svpStudy = studies.find(s => s.name && s.name.includes('SVP'));
  if (svpStudy) {
    const v = svpStudy.values;
    const titleMap = {
      'S VWAP': 'vwap',
      'S VWAP +Band1': 'band1_high',
      'S VWAP -Band1': 'band1_low',
      'S VWAP +Band2': 'band2_high',
      'S VWAP -Band2': 'band2_low',
      'Weekly VWAP Data': 'w_vwap',
      'Monthly VWAP Data': 'm_vwap',
      'EMA 9': 'ema9',
      'EMA 21': 'ema21',
      'EMA 34': 'ema34',
      'EMA 55': 'ema55',
      'CVD Value': 'cvd',
      'CVD Slope': 'cvd_slope',
      'POC Price': 'poc',
      'VAH Price': 'vah',
      'VAL Price': 'valPrice',
      'DO Price': 'dopen',
    };
    for (const [title, field] of Object.entries(titleMap)) {
      const rawVal = v[title];
      if (rawVal !== undefined) {
        const parsed = parseTVValue(rawVal);
        if (parsed !== null) {
          switch (field) {
            case 'vwap': vwap = parsed; break;
            case 'band1_high': band1_high = parsed; break;
            case 'band1_low': band1_low = parsed; break;
            case 'band2_high': band2_high = parsed; break;
            case 'band2_low': band2_low = parsed; break;
            case 'w_vwap': w_vwap = parsed; break;
            case 'm_vwap': m_vwap = parsed; break;
            case 'ema9': ema9 = parsed; break;
            case 'ema21': ema21 = parsed; break;
            case 'ema34': ema34 = parsed; break;
            case 'ema55': ema55 = parsed; break;
            case 'cvd': cvd = parsed; break;
            case 'cvd_slope': cvd_slope = parsed; break;
            case 'poc': poc = parsed; break;
            case 'vah': vah = parsed; break;
            case 'valPrice': valPrice = parsed; break;
            case 'dopen': dopen = parsed; break;
          }
        }
      }
    }
  }

  // Get pine lines
  let linesRaw = JSON.parse(await evaluate(client, `
    (function() {
      var chart = window.TradingViewApi._activeChartWidgetWV.value()._chartWidget;
      var model = chart.model();
      var sources = model.model().dataSources();
      var results = [];
      for (var si = 0; si < sources.length; si++) {
        var s = sources[si];
        if (!s.metaInfo) continue;
        try {
          var meta = s.metaInfo();
          var name = meta.description || meta.shortDescription || '';
          if (!name) continue;
          var g = s._graphics;
          if (!g || !g._primitivesCollection) continue;
          var pc = g._primitivesCollection;
          var items = [];
          try {
            var outer = pc.dwglines;
            if (outer) {
              var inner = outer.get('lines');
              if (inner) {
                var coll = inner.get(false);
                if (coll && coll._primitivesDataById && coll._primitivesDataById.size > 0) {
                  coll._primitivesDataById.forEach(function(v, id) { items.push({id: id, raw: v}); });
                }
              }
            }
          } catch(e) {}
          if (items.length > 0) results.push({name: name, count: items.length, items: items});
        } catch(e) {}
      }
      return JSON.stringify(results);
    })()
  `));
  linesRaw = JSON.parse(linesRaw);

  const allLevels = new Set();
  const allLines = [];
  for (const study of linesRaw) {
    for (const item of study.items) {
      const v = item.raw;
      const y1 = v.y1 != null ? Math.round(v.y1 * 100) / 100 : null;
      const y2 = v.y2 != null ? Math.round(v.y2 * 100) / 100 : null;
      if (y1 != null && y1 === y2 && !allLevels.has(y1)) {
        allLevels.add(y1);
        allLines.push(y1);
      }
    }
  }
  allLines.sort((a, b) => b - a);

  // Get pine labels
  let labelsRaw = JSON.parse(await evaluate(client, `
    (function() {
      var chart = window.TradingViewApi._activeChartWidgetWV.value()._chartWidget;
      var model = chart.model();
      var sources = model.model().dataSources();
      var results = [];
      for (var si = 0; si < sources.length; si++) {
        var s = sources[si];
        if (!s.metaInfo) continue;
        try {
          var meta = s.metaInfo();
          var name = meta.description || meta.shortDescription || '';
          if (!name) continue;
          var g = s._graphics;
          if (!g || !g._primitivesCollection) continue;
          var pc = g._primitivesCollection;
          var items = [];
          try {
            var outer = pc.dwglabels;
            if (outer) {
              var inner = outer.get('labels');
              if (inner) {
                var coll = inner.get(false);
                if (coll && coll._primitivesDataById && coll._primitivesDataById.size > 0) {
                  coll._primitivesDataById.forEach(function(v, id) { items.push({id: id, raw: v}); });
                }
              }
            }
          } catch(e) {}
          if (items.length > 0) results.push({name: name, count: items.length, items: items});
        } catch(e) {}
      }
      return JSON.stringify(results);
    })()
  `));
  labelsRaw = JSON.parse(labelsRaw);

  const allLabels = [];
  for (const study of labelsRaw) {
    let labels = study.items.map(item => {
      const v = item.raw;
      const text = v.t || '';
      const price = v.y != null ? Math.round(v.y * 100) / 100 : null;
      return { text, price };
    }).filter(l => l.text || l.price != null);
    if (labels.length > 20) labels = labels.slice(-20);
    allLabels.push(...labels);
  }
  const seenPrices = new Set();
  const uniqueLabels = [];
  for (const l of allLabels) {
    const key = l.price + '|' + l.text;
    if (!seenPrices.has(key)) {
      seenPrices.add(key);
      uniqueLabels.push(l);
    }
  }

  // Get pine tables for tv_grade and tv_treatment
  let tv_grade = null, tv_treatment = null;
  try {
    let tablesRaw = JSON.parse(await evaluate(client, `
      (function() {
        var chart = window.TradingViewApi._activeChartWidgetWV.value()._chartWidget;
        var model = chart.model();
        var sources = model.model().dataSources();
        var results = [];
        for (var si = 0; si < sources.length; si++) {
          var s = sources[si];
          if (!s.metaInfo) continue;
          try {
            var meta = s.metaInfo();
            var name = meta.description || meta.shortDescription || '';
            if (!name) continue;
            var g = s._graphics;
            if (!g || !g._primitivesCollection) continue;
            var pc = g._primitivesCollection;
            var tables = [];
            try {
              var outer = pc.dwglabels;
              if (outer) {
                var inner = outer.get('tables');
                if (inner) {
                  var coll = inner.get(false);
                  if (coll && coll._primitivesDataById && coll._primitivesDataById.size > 0) {
                    coll._primitivesDataById.forEach(function(v, id) {
                      if (v && v._rows) tables.push({ id: id, rows: v._rows });
                    });
                  }
                }
              }
            } catch(e) {}
            if (tables.length > 0) results.push({ name: name, tables: tables });
          } catch(e) {}
        }
        return JSON.stringify(results);
      })()
    `));
    tablesRaw = JSON.parse(tablesRaw);
    for (const study of tablesRaw) {
      if (study.name && study.name.includes('SVP')) {
        for (const table of study.tables) {
          if (table.rows) {
            for (const row of table.rows) {
              if (typeof row === 'string') {
                const parts = row.split('|').map(s => s.trim());
                if (parts[0] === '等级' && parts[1]) tv_grade = parts[1];
                if (parts[0] === '处理' && parts[1]) tv_treatment = parts[1];
              }
            }
          }
        }
      }
    }
  } catch(e) {}

  const output = {
    timestamp: new Date().toISOString(),
    symbol: TARGET_SYMBOL,
    resolution,
    vwap,
    band1_high, band1_low, band2_high, band2_low,
    w_vwap, m_vwap,
    ema9, ema21, ema34, ema55,
    cvd, cvd_slope,
    poc, vah, val: valPrice, dopen,
    levels: allLines,
    labels: uniqueLabels,
    tv_grade, tv_treatment,
  };

  const outputFile = path.join(OUTPUT_BASE, `${ticker}_tv_${resolution}.json`);
  fs.writeFileSync(outputFile, JSON.stringify(output, null, 2), 'utf8');
  console.log(`Written to ${outputFile}`);
  return output;
}

async function main() {
  let target = null;
  const targets = await CDP.List({ port: 9222 });
  for (const t of targets) {
    if (t.title && t.title.includes('TradingView') && t.url && t.url.includes('chart')) {
      target = t;
      break;
    }
  }
  if (!target) {
    for (const t of targets) {
      if (t.type === 'page' && t.title && (t.title.includes('TradingView') || t.title.includes('chart'))) {
        target = t;
        break;
      }
    }
  }
  if (!target) {
    console.error('No TradingView chart target found');
    process.exit(1);
  }

  const client = await CDP({ port: 9222, target: target.id });
  await client.Runtime.enable();
  await client.Page.enable();

  try {
    // First ensure correct symbol
    const chart = 'window.TradingViewApi._activeChartWidgetWV.value()';
    const state = JSON.parse(await evaluate(client, `
      (function() {
        var c = ${chart};
        return JSON.stringify({ symbol: c.symbol(), resolution: c.resolution() });
      })()
    `));
    
    if (state.symbol !== TARGET_SYMBOL) {
      console.log('Setting symbol...');
      await evaluate(client, `
        (function() {
          var c = ${chart};
          c.setSymbol(${safeString(TARGET_SYMBOL)}, function() {});
        })()
      `);
      await sleep(3500);
    }

    const results = {};
    for (const tf of TIMEFRAMES) {
      results[tf] = await fetchTF(client, tf);
    }

    // Save combined
    const combined = {
      timestamp: new Date().toISOString(),
      symbol: TARGET_SYMBOL,
      timeframes: results,
    };
    fs.writeFileSync(path.join(OUTPUT_BASE, `${ticker}_tv_multi.json`), JSON.stringify(combined, null, 2), 'utf8');
    console.log('\n=== All timeframes fetched successfully ===');
    
    // Print summary
    for (const [tf, data] of Object.entries(results)) {
      console.log(`\n${tf}m:`);
      console.log(`  VWAP: ${data.vwap} | POC: ${data.poc} | CVD: ${data.cvd}`);
      console.log(`  EMA9/21/34/55: ${data.ema9}/${data.ema21}/${data.ema34}/${data.ema55}`);
      console.log(`  VAH: ${data.vah} | VAL: ${data.val}`);
    }
  } catch (err) {
    console.error('Error:', err.message);
    process.exit(1);
  } finally {
    client.close();
  }
}

main();
