#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""中转 / 供应商能力探针（只读，不改配置）。

形状取自 2026-09-13 在 b.ai 中转与 OpenRouter 免费池上实跑的探针代码：
  模型存不存在 / 支不支持 function tools / 端点是不是坏的 / 是不是 reasoning 吃光了输出预算。

用法:
  python relay_capability_probe.py                                     # 默认探 b.ai 三个登记模型
  python relay_capability_probe.py b.ai deepseek-v4.1-flash gpt-6-astra kimi-k3
  python relay_capability_probe.py openrouter nvidia/nemotron-3.5-lightning:free
  python relay_capability_probe.py b.ai deepseek-v4.1-flash --img D:/x/shot.png --max-tokens 6000

判定:
  TOOLS_OK                 真 tool_calls 且 arguments 是含 path 的合法 JSON
  TOOLS_NO_ARG             有 tool_calls 但参数不合法
  TEXT_ONLY                不带 tools 能答、带 tools 不调 → 工具不可用
  REASONING_TOOLS_CONFLICT 400 且报错含 reasoning_effort（改 none 或走 /v1/responses）
  EMPTY_REASONING_BUDGET   200 + 空 content + finish=length → 提高 --max-tokens 重探
  BROKEN_ENDPOINT          200 但 model/usage/finish 全空 → 别放进链路
  RATE_LIMITED / HTTP_4xx / ERR_*

出现 HTTP_4xx 或 REASONING_TOOLS_CONFLICT 时会自动补一枪「不带 tools」对照，
用来区分「这个模型在这个端点不支持工具」与「模型根本不存在/凭据有问题」。
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import time
import urllib.error
import urllib.request

HERMES = os.path.join(os.path.expanduser('~'), 'AppData', 'Local', 'hermes')
CONFIG = os.path.join(HERMES, 'config.yaml')
ENVDOT = os.path.join(HERMES, '.env')

TOOLS = [{
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "读取本地文件内容",
        "parameters": {"type": "object",
                       "properties": {"path": {"type": "string"}},
                       "required": ["path"]},
    },
}]
TEXT_PROMPT = "用 read_file 工具读取 D:/Hermes agent/docs/系统总览.md，path 用完整路径。先调用工具，不要先用文字回答。"
IMG_PROMPT = "看图：1)品种 2)周期 3)最新价 4)副图数量与名称。简短回答。"


def endpoint(provider):
    """openrouter → .env 的 OPENROUTER_API_KEY；其它 → config.yaml 的 custom_providers 段。"""
    if provider == 'openrouter':
        m = re.search(r'OPENROUTER_API_KEY=(sk-or-[A-Za-z0-9_\-]+)',
                      open(ENVDOT, encoding='utf-8').read())
        if not m:
            raise SystemExit('在 .env 里找不到 OPENROUTER_API_KEY')
        return 'https://openrouter.ai/api/v1', m.group(1)
    cfg = open(CONFIG, encoding='utf-8').read()
    m = re.search(r'custom_providers:.*?base_url:\s*"([^"]+)".*?api_key:\s*"([^"]+)"', cfg, re.S)
    if not m:
        raise SystemExit('在 config.yaml 的 custom_providers 里找不到 base_url/api_key')
    return m.group(1), m.group(2)


def call(base, key, model, max_tokens, img=None, with_tools=True):
    prompt = IMG_PROMPT if img else TEXT_PROMPT
    if img:
        data_url = 'data:image/png;base64,' + base64.b64encode(open(img, 'rb').read()).decode()
        content = [{"type": "text", "text": prompt},
                   {"type": "image_url", "image_url": {"url": data_url}}]
    else:
        content = prompt
    body = {"model": model, "messages": [{"role": "user", "content": content}],
            "max_tokens": max_tokens}
    if with_tools:
        body["tools"] = TOOLS
    req = urllib.request.Request(base.rstrip('/') + '/chat/completions',
                                 data=json.dumps(body).encode('utf-8'),
                                 headers={'Authorization': 'Bearer ' + key,
                                          'Content-Type': 'application/json'})
    t0 = time.time()
    try:
        resp = urllib.request.urlopen(req, timeout=300)
        return resp.status, round(time.time() - t0, 1), json.loads(resp.read()), ''
    except urllib.error.HTTPError as e:
        return e.code, round(time.time() - t0, 1), None, e.read()[:300].decode('utf-8', 'replace')
    except Exception as e:                      # 探针要吞掉所有网络异常，逐模型降级
        return 'ERR', round(time.time() - t0, 1), None, type(e).__name__ + ': ' + str(e)[:120]


def verdict(status, payload, err):
    if status == 429:
        return 'RATE_LIMITED', err[:120]
    if status != 200 or payload is None:
        if 'reasoning_effort' in err:
            return 'REASONING_TOOLS_CONFLICT', err[:150]
        return 'HTTP_%s' % status, err[:150]
    choice = (payload.get('choices') or [{}])[0]
    msg = choice.get('message') or {}
    usage = payload.get('usage') or {}
    detail = usage.get('completion_tokens_details') or {}
    tool_calls = msg.get('tool_calls') or []
    content = (msg.get('content') or '').strip()
    reasoning = (msg.get('reasoning_content') or msg.get('reasoning') or '').strip()
    if payload.get('model') is None and not usage and choice.get('finish_reason') is None:
        return 'BROKEN_ENDPOINT', 'ret_model/usage/finish 全空'
    if tool_calls:
        try:
            args = json.loads(tool_calls[0].get('function', {}).get('arguments') or '{}')
        except Exception:
            args = {}
        ok = isinstance(args.get('path'), str) and bool(args['path'].strip())
        return ('TOOLS_OK' if ok else 'TOOLS_NO_ARG'), json.dumps(args, ensure_ascii=False)[:80]
    if content:
        return 'TEXT_ONLY', content[:80]
    if choice.get('finish_reason') == 'length' or detail.get('reasoning_tokens'):
        return 'EMPTY_REASONING_BUDGET', 'reasoning_tokens=%s（提高 --max-tokens 重探）' % detail.get('reasoning_tokens')
    return 'EMPTY', (reasoning[:80] or '无 content、无 reasoning')


def row(model, status, lat, tag, detail, prefix=''):
    print('%s%-46s %-6s %6ss  %-24s %s' % (prefix, model, status, lat, tag, detail))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('provider', nargs='?', default='b.ai')
    ap.add_argument('models', nargs='*')
    ap.add_argument('--img', default=None, help='真图夹具路径（PNG）；不给则跑文本/工具探针')
    ap.add_argument('--max-tokens', type=int, default=1500, help='文本 1500 起步；读图 >=3000')
    args = ap.parse_args()

    base, key = endpoint(args.provider)
    models = args.models or ['deepseek-v4.1-flash', 'gpt-6-astra', 'glm-5.3-flash']
    print('endpoint=%s | models=%d | max_tokens=%d | img=%s'
          % (base, len(models), args.max_tokens, args.img or '-'))

    conflicts = []
    for model in models:
        status, lat, payload, err = call(base, key, model, args.max_tokens, img=args.img)
        tag, detail = verdict(status, payload, err)
        row(model, status, lat, tag, detail)
        if tag == 'REASONING_TOOLS_CONFLICT' or tag.startswith('HTTP_4'):
            conflicts.append(model)

    if conflicts:
        print('\n对照（同一模型不带 tools，用于区分「该端点不支持工具」与「模型不存在/凭据问题」）:')
        for model in conflicts:
            status, lat, payload, err = call(base, key, model, args.max_tokens,
                                            img=args.img, with_tools=False)
            tag, detail = verdict(status, payload, err)
            row(model, status, lat, tag, detail, prefix='  ')


if __name__ == '__main__':
    main()
