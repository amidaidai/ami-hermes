---
name: guizang-ppt-skill
category: community
description: "横向翻页网页PPT（单HTML文件），含WebGL背景、多种模板。"
---

# 鬼葬PPT — 横向翻页网页PPT

横向翻页网页PPT（单HTML文件），含WebGL动态背景和多种模板。无需任何外部依赖，在浏览器中直接打开即可演示。

## 特点

- 单HTML文件，零依赖
- 横向翻页（左右箭头/空格/滑动）
- WebGL 动态背景（粒子、星空、波浪等）
- 多种内置模板样式
- 自动适应屏幕大小

## 快速开始

```html
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>我的演示</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: 'Microsoft YaHei', sans-serif; overflow: hidden; background: #0a0a1a; }
  
  #canvas-bg { position: fixed; top: 0; left: 0; width: 100%; height: 100%; z-index: 0; }
  
  .slides-container {
    position: relative; z-index: 1;
    display: flex; overflow-x: auto; scroll-snap-type: x mandatory;
    height: 100vh; scrollbar-width: none;
  }
  .slides-container::-webkit-scrollbar { display: none; }
  
  .slide {
    min-width: 100vw; height: 100vh;
    display: flex; align-items: center; justify-content: center;
    flex-direction: column; scroll-snap-align: start;
    color: white; padding: 5%;
  }
  
  .slide h1 { font-size: 3em; margin-bottom: 0.5em; text-shadow: 0 0 20px rgba(255,255,255,0.3); }
  .slide p { font-size: 1.3em; max-width: 800px; line-height: 1.6; }
  .slide ul { font-size: 1.2em; list-style: none; }
  .slide ul li { margin: 0.8em 0; padding-left: 1.5em; position: relative; }
  .slide ul li::before { content: '▸'; position: absolute; left: 0; color: #64ffda; }
  
  .template-card {
    background: rgba(255,255,255,0.08); backdrop-filter: blur(10px);
    border: 1px solid rgba(255,255,255,0.1); border-radius: 16px;
    padding: 2em; max-width: 800px;
  }
</style>
</head>
<body>

<canvas id="canvas-bg"></canvas>

<div class="slides-container" id="slides">
  <div class="slide">
    <div class="template-card" style="text-align:center;">
      <h1>鬼葬PPT</h1>
      <p>横向翻页 · WebGL 动态背景</p>
      <p style="font-size:0.9em; opacity:0.6;">按 → 或 Space 继续</p>
    </div>
  </div>
  
  <div class="slide">
    <div class="template-card">
      <h2>目录</h2>
      <ul>
        <li>项目概述</li>
        <li>技术架构</li>
        <li>核心功能</li>
        <li>演示与效果</li>
      </ul>
    </div>
  </div>
  
  <div class="slide">
    <div class="template-card">
      <h2>项目概述</h2>
      <p>这是一个使用 HTML + WebGL 构建的演示文稿，支持动态粒子背景，无需 PowerPoint 或其他软件。</p>
    </div>
  </div>
</div>

<!-- WebGL Particle Background -->
<script>
const canvas = document.getElementById('canvas-bg');
const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');

function resize() {
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
  gl.viewport(0, 0, canvas.width, canvas.height);
}
window.addEventListener('resize', resize);
resize();

// Simple WebGL particle shader
const vs = `
  attribute vec2 position;
  void main() { gl_Position = vec4(position, 0.0, 1.0); }
`;

const fs = `
  precision highp float;
  uniform vec2 resolution;
  uniform float time;
  void main() {
    vec2 uv = gl_FragCoord.xy / resolution;
    vec3 color = vec3(0.1, 0.1, 0.3);
    for (int i = 0; i < 3; i++) {
      vec2 p = vec2(
        sin(time * 0.1 + float(i) * 2.0) * 0.5 + 0.5,
        cos(time * 0.08 + float(i) * 3.0) * 0.5 + 0.5
      );
      float d = distance(uv, p);
      color += vec3(0.05, 0.1, 0.2) / (d * 3.0);
    }
    gl_FragColor = vec4(color, 1.0);
  }
`;

// Compile shader program
function initShader(gl, vsSrc, fsSrc) {
  const vsShader = gl.createShader(gl.VERTEX_SHADER);
  gl.shaderSource(vsShader, vsSrc);
  gl.compileShader(vsShader);
  const fsShader = gl.createShader(gl.FRAGMENT_SHADER);
  gl.shaderSource(fsShader, fsSrc);
  gl.compileShader(fsShader);
  const program = gl.createProgram();
  gl.attachShader(program, vsShader);
  gl.attachShader(program, fsShader);
  gl.linkProgram(program);
  return program;
}

const program = initShader(gl, vs, fs);
gl.useProgram(program);

const vertices = new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]);
const buffer = gl.createBuffer();
gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
gl.bufferData(gl.ARRAY_BUFFER, vertices, gl.STATIC_DRAW);

const posAttr = gl.getAttribLocation(program, 'position');
gl.enableVertexAttribArray(posAttr);
gl.vertexAttribPointer(posAttr, 2, gl.FLOAT, false, 0, 0);

const timeUniform = gl.getUniformLocation(program, 'time');
const resUniform = gl.getUniformLocation(program, 'resolution');

function render(time) {
  gl.uniform1f(timeUniform, time / 1000);
  gl.uniform2f(resUniform, canvas.width, canvas.height);
  gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
  requestAnimationFrame(render);
}
requestAnimationFrame(render);

// Keyboard navigation
let slideIndex = 0;
const slides = document.querySelectorAll('.slide');
const container = document.getElementById('slides');

document.addEventListener('keydown', (e) => {
  if (e.key === 'ArrowRight' || e.key === ' ') {
    slideIndex = Math.min(slideIndex + 1, slides.length - 1);
    container.scrollTo({ left: slideIndex * window.innerWidth, behavior: 'smooth' });
  } else if (e.key === 'ArrowLeft') {
    slideIndex = Math.max(slideIndex - 1, 0);
    container.scrollTo({ left: slideIndex * window.innerWidth, behavior: 'smooth' });
  }
});
</script>
</body>
</html>
```

## 内置模板

- **暗色科技风** — 深色背景 + 发光粒子
- **渐变唯美风** — 柔和渐变色背景
- **星空风** — WebGL 星空粒子背景
- **极简白** — 浅色背景简洁风格
- **卡片风** — 毛玻璃卡片布局

## 快捷键

| 按键 | 功能 |
|------|------|
| → / Space | 下一页 |
| ← | 上一页 |
| Home | 首页 |
| End | 末页 |
| F | 全屏 |

## Pitfalls

- WebGL 在部分浏览器上可能不支持，建议添加 fallback CSS 背景
- 中文文本建议使用系统字体（Microsoft YaHei, PingFang SC）以确保在不同系统上正常显示
- 大量粒子（>500）在移动设备上可能性能下降
- 翻页惯性滚动可能导致定位不精确，使用 scroll-snap 可以缓解

## Verification

在 Chrome 中打开 HTML 文件，确认：
1. WebGL 背景正常渲染（彩色动态粒子）
2. 按 → 键可以翻到下一页
3. 按 ← 键可以返回上一页
4. 页面宽高比自适应
