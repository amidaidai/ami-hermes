/**
 * PPTX Generation Template — pptxgenjs + sharp
 * 
 * Proven structure for producing professional 33-page government training decks.
 * Copy this file and modify content/color scheme for your specific topic.
 * 
 * Key features:
 * - 16:9 widescreen (13.333" x 7.5")
 * - Reusable helper functions (addText, rect, line, image, metric, callout, etc.)
 * - Sharp-based image preprocessing (cover/contain, quality control)
 * - Consistent footer with source citations and slide numbers
 * - Dark section dividers with photo backgrounds
 * - Color palette object for easy theming
 * - Speaker notes on every slide
 */

const pptxgen = require('pptxgenjs');
const sharp = require('sharp');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const ASSETS = path.join(ROOT, 'assets');
const PREP = path.join(ASSETS, 'prepared');
const OUTPUT = path.join(ROOT, 'output');
const OUT_FILE = path.join(OUTPUT, 'your_deck_name.pptx');

const W = 13.333;
const H = 7.5;
const FONT = 'Microsoft YaHei';

// Color palette — customize for your topic
const C = {
  ink: '1E2B28',
  ink2: '31413C',
  green: '2F6B4F',
  green2: '4E8A68',
  greenPale: 'E8F1EB',
  blue: '245B78',
  bluePale: 'E7F0F4',
  red: 'B64A3A',
  redPale: 'F6E9E6',
  gold: 'C49135',
  goldPale: 'F7F0E1',
  gray: '68736F',
  gray2: '96A09C',
  line: 'D9DEDB',
  bg: 'F5F7F5',
  white: 'FFFFFF',
  black: '000000',
};

// Source URLs for hyperlinks and citations
const SRC = {
  // Add your source URLs here
};

const dataOwner = 'your organization name';

// ─── Helper Functions ───

function addText(slide, text, x, y, w, h, opts = {}) {
  slide.addText(text, {
    x, y, w, h,
    fontFace: FONT,
    fontSize: 16,
    color: C.ink,
    margin: 0,
    breakLine: false,
    valign: 'mid',
    fit: 'shrink',
    ...opts,
  });
}

function rect(slide, x, y, w, h, fill, line = fill, radius = false, transparency = 0) {
  slide.addShape(radius ? pptx.ShapeType.roundRect : pptx.ShapeType.rect, {
    x, y, w, h,
    fill: { color: fill, transparency },
    line: { color: line, transparency: line === fill ? 100 : 0, width: 0.8 },
  });
}

function line(slide, x, y, w, h, color = C.line, width = 1, dash = 'solid', beginArrowType, endArrowType) {
  slide.addShape(pptx.ShapeType.line, {
    x, y, w, h,
    line: { color, width, dashType: dash, beginArrowType, endArrowType },
  });
}

function image(slide, file, x, y, w, h, altText, mode = 'cover', hyperlink) {
  slide.addImage({
    path: file,
    x, y, w, h,
    sizing: { type: mode, w, h },
    altText: altText || path.basename(file),
    hyperlink: hyperlink ? { url: hyperlink } : undefined,
  });
}

function addFooter(slide, slideNo, source = '', section = '') {
  line(slide, 0.45, 7.06, 12.43, 0, C.line, 0.7);
  addText(slide, section || 'Your Deck Name', 0.48, 7.1, 3.3, 0.2, {
    fontSize: 8.5, color: C.gray, valign: 'mid',
  });
  addText(slide, source, 3.35, 7.1, 8.95, 0.2, {
    fontSize: 8.2, color: C.gray, align: 'right', valign: 'mid',
  });
  addText(slide, String(slideNo).padStart(2, '0'), 12.47, 7.08, 0.4, 0.22, {
    fontSize: 9, color: C.green, bold: true, align: 'right',
  });
}

function addTitle(slide, title, slideNo, opts = {}) {
  rect(slide, 0.46, 0.42, 0.08, 0.42, opts.accent || C.green);
  addText(slide, title, 0.68, 0.34, 9.9, 0.62, {
    fontFace: FONT, fontSize: opts.fontSize || 27, bold: true, color: C.ink,
  });
  if (opts.kicker) {
    addText(slide, opts.kicker, 10.25, 0.43, 2.55, 0.3, {
      fontSize: 10.5, color: opts.accent || C.green, bold: true, align: 'right',
    });
  }
  addFooter(slide, slideNo, opts.source || '', opts.section || 'Your Deck Name');
}

function tag(slide, text, x, y, w, fill = C.greenPale, color = C.green) {
  rect(slide, x, y, w, 0.34, fill, fill, true);
  addText(slide, text, x + 0.1, y + 0.02, w - 0.2, 0.29, {
    fontSize: 10.5, bold: true, color, align: 'center',
  });
}

function metric(slide, x, y, w, h, value, label, accent = C.green, sub = '') {
  rect(slide, x, y, w, h, C.white, C.line, false);
  rect(slide, x, y, 0.08, h, accent);
  addText(slide, value, x + 0.22, y + 0.18, w - 0.38, h * 0.45, {
    fontSize: 25, bold: true, color: accent,
  });
  addText(slide, label, x + 0.22, y + h * 0.56, w - 0.38, 0.3, {
    fontSize: 11.5, bold: true, color: C.ink2,
  });
  if (sub) addText(slide, sub, x + 0.22, y + h - 0.34, w - 0.38, 0.22, { fontSize: 8.5, color: C.gray });
}

function bulletList(slide, items, x, y, w, h, opts = {}) {
  const fontSize = opts.fontSize || 14;
  const runs = items.map((item, idx) => {
    const value = typeof item === 'string' ? item : item.text;
    return {
      text: value,
      options: {
        bullet: { code: opts.bulletCode || '2022' },
        breakLine: idx < items.length - 1,
        color: typeof item === 'string' ? (opts.color || C.ink) : (item.color || opts.color || C.ink),
        bold: typeof item === 'string' ? false : Boolean(item.bold),
        fontSize,
        paraSpaceAfterPt: opts.paraSpaceAfterPt || 10,
      },
    };
  });
  addText(slide, runs, x, y, w, h, { fontSize, valign: 'top', margin: [0.03, 0.08, 0.03, 0.08], breakLine: undefined });
}

function callout(slide, x, y, w, h, title, body, accent = C.green, fill = C.white) {
  rect(slide, x, y, w, h, fill, C.line, false);
  rect(slide, x, y, w, 0.08, accent);
  addText(slide, title, x + 0.18, y + 0.2, w - 0.36, 0.35, { fontSize: 14, bold: true, color: accent });
  addText(slide, body, x + 0.18, y + 0.65, w - 0.36, h - 0.82, { fontSize: 11.5, color: C.ink2, valign: 'top', breakLine: undefined, margin: [0.02, 0, 0.02, 0] });
}

function hBar(slide, x, y, w, value, max, color, label, valueLabel, bg = 'E8ECEA') {
  addText(slide, label, x, y - 0.02, 2.25, 0.28, { fontSize: 11.5, bold: true });
  rect(slide, x + 2.25, y + 0.02, w - 3.3, 0.22, bg, bg, true);
  rect(slide, x + 2.25, y + 0.02, (w - 3.3) * Math.min(value / max, 1), 0.22, color, color, true);
  addText(slide, valueLabel, x + w - 0.98, y - 0.05, 0.98, 0.32, { fontSize: 11.5, bold: true, color, align: 'right' });
}

function sectionDivider(slide, no, title, subtitle, photo, sourceUrl) {
  slide.background = { color: C.ink };
  image(slide, photo, 0, 0, W, H, title, 'cover', sourceUrl);
  rect(slide, 0, 0, W, H, C.black, C.black, false, 42);
  rect(slide, 0.68, 1.03, 0.1, 4.94, C.gold);
  addText(slide, no, 1.05, 1.08, 1.35, 0.75, { fontSize: 39, bold: true, color: C.gold });
  addText(slide, title, 1.05, 2.02, 7.6, 1.0, { fontSize: 34, bold: true, color: C.white });
  addText(slide, subtitle, 1.06, 3.23, 7.7, 1.0, { fontSize: 16, color: C.white, valign: 'top' });
  addText(slide, 'Your Organization', 1.06, 5.55, 3.3, 0.35, { fontSize: 12, color: C.white, bold: true });
}

// ─── Image Preprocessing ───

async function prepImage(srcName, outName, width, height, position = 'centre', quality = 88) {
  const out = path.join(PREP, outName);
  await sharp(path.join(ASSETS, srcName))
    .rotate()
    .resize(width, height, { fit: 'cover', position })
    .jpeg({ quality, mozjpeg: true })
    .toFile(out);
  return out;
}

async function prepareAssets() {
  fs.mkdirSync(PREP, { recursive: true });
  fs.mkdirSync(OUTPUT, { recursive: true });
  // Add your image preprocessing calls here
  const prepared = {};
  // prepared.cover = await prepImage('photo.jpg', 'cover.jpg', 1920, 1080, 'centre');
  return prepared;
}

// ─── Build ───

const pptx = new pptxgen();
pptx.layout = 'LAYOUT_WIDE';
pptx.author = 'Your Organization';
pptx.company = 'Your Organization';
pptx.subject = 'Your Subject';
pptx.title = 'Your Title';
pptx.lang = 'zh-CN';

async function build() {
  const A = await prepareAssets();
  let n = 0;

  // Cover slide
  {
    const slide = pptx.addSlide(); n += 1;
    slide.background = { color: C.ink };
    // ... add content
    slide.addNotes('Speaker notes here');
  }

  // Add more slides here...

  await pptx.writeFile({ fileName: OUT_FILE, compression: true });
  console.log(`Wrote ${OUT_FILE}`);
  console.log(`Slides: ${n}`);
}

build().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});