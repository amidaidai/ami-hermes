from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import 模型统计 as ms


def test_fnum_helper():
    assert ms.fnum("2.0") == 2.0
    assert ms.fnum(None) == 0.0
    assert ms.fnum("") == 0.0


def test_review_model_key_prefers_model_id():
    # 自动标注 review 用 model_id，旧手动 review 用 model；两者都要能取到
    auto = {"model_id": "VWAP反抽", "result_r": 2.0}
    manual = {"model": "VAL回收", "r_multiple": -1.0}
    assert ms.review_model_key(auto) == "VWAP反抽"
    assert ms.review_model_key(manual) == "VAL回收"


def test_review_r_prefers_result_r():
    # 自动标注用 result_r，旧手动用 r_multiple
    auto = {"model_id": "VWAP反抽", "result_r": 2.0}
    manual = {"model": "VAL回收", "r_multiple": -1.0}
    assert ms.review_r(auto) == 2.0
    assert ms.review_r(manual) == -1.0


def test_autolabeled_reviews_grouped_and_counted(tmp_path, monkeypatch):
    # 端到端：3 笔自动标注 review → 按 model_id 分组、result_r 计胜负
    reviews = [
        {"model_id": "VWAP反抽", "result_r": 2.0, "was_correct": True, "auto_labeled": True},
        {"model_id": "VWAP反抽", "result_r": -1.0, "was_correct": False, "auto_labeled": True},
        {"model_id": "VAL回收", "result_r": 2.0, "was_correct": True, "auto_labeled": True},
    ]
    grouped = ms.group_reviews(reviews)
    assert "VWAP反抽" in grouped
    assert len(grouped["VWAP反抽"]) == 2
    assert "VAL回收" in grouped
    # VWAP反抽: 1 win 1 loss → win_rate 0.5
    rs = [ms.review_r(r) for r in grouped["VWAP反抽"]]
    wins = sum(1 for r in rs if r > 0)
    assert wins == 1
