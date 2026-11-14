"""CAL-02：参数落值——**本卡的结论是「今天一个参数都标定不了」，并给出证据**。

## 先定评价口径，再调参（acceptance②）

「NEVER 反推阈值凑指标」这条红线在本卡有一个结构上的落法：
评价口径（用哪批金标、算什么指标、多少算过线）**先写进 `CALIBRATION_CALIBER` 并落指纹**，
扫参在后。调完不许再动口径——动了，指纹就对不上，测试红。

## 四个参数，四种「标不了」的理由（都有实测撑着）

| 参数 | 今天能不能标 | 证据 |
|---|---|---|
| `theta_rel` | **不能** | 它是**每个查询**的 `hit_rate`（top-k 里相关的比例）的阈值，而金标是**逐对**的相关标注——形状不对，不是数量不够 |
| `delta` | **不能** | demo 库的关键词嵌入**没有语义信号**：任意两词余弦距离均值 1.0001、标准差 0.031（1024 维随机向量的特征）；扫出来的最优 F1 只有 0.22，且 `same` 对比 `different` 对**还远** |
| `hotness.*` | **不能** | 没有任何金标序列；`harness/tune_hotness.py` 一直是 report_only |
| 血缘 ≥90%/50 簇 | **测得出但判不了** | CAL-01 实测 60/60 簇 correct，但那批语料**一次簇漂移都没有**——判不出错不等于没错 |

## 所以本卡改的是「标定状态」，不是参数值

`flint/config.py` 多一张 `CALIBRATION_STATUS` 表：逐参数写明**标没标定、为什么、
证据在哪、样本量、日期**。BL-05 的未标定标记因此**不清除**——
清除它等于宣称标定过了，而本卡的结论恰恰相反。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from flint.config import (
    CALIBRATION_CALIBER,
    CALIBRATION_STATUS,
    caliber_fingerprint,
    load_tuning,
)

REPO = Path(__file__).resolve().parents[2]
DOC = REPO / "docs" / "参数标定-v041.md"
GOLDSETS = REPO / "assets" / "goldsets"

PARAMS = ("theta_rel", "delta", "hotness", "lineage_accuracy")


# ───────────────────────── 一、先定口径再调参（acceptance②）


def test_the_caliber_is_written_down_before_any_number() -> None:
    """评价口径**先写清**：用哪批金标、算什么指标、多少算过线。

    不先定的话，「调参」与「挑一个让指标好看的数」在过程上分不开——
    这正是红线「NEVER 反推阈值凑指标」要防的那件事。
    """
    for param in PARAMS:
        caliber = CALIBRATION_CALIBER[param]
        assert caliber["goldset"], f"{param} 没写用哪批金标"
        assert caliber["metric"], f"{param} 没写算什么指标"
        assert len(caliber["pass_line"]) >= 4, f"{param} 没写多少算过线"


def test_the_caliber_carries_a_fingerprint() -> None:
    """口径有指纹：调完再改口径，指纹就对不上。"""
    assert len(caliber_fingerprint()) == 64


def test_the_document_records_the_same_fingerprint() -> None:
    """文档里记的口径指纹 = 代码里的当前口径。

    对不上就说明**口径在出数之后被动过**——那份对照表就不能信了。
    """
    doc = DOC.read_text(encoding="utf-8")
    stated = next(ln.split(":", 1)[1].strip() for ln in doc.splitlines()
                  if ln.startswith("caliber_sha256:"))

    assert stated == caliber_fingerprint()


# ───────────────────────── 二、结论：一个都没标定（acceptance③）


@pytest.mark.parametrize("param", PARAMS)
def test_every_param_has_a_status_entry(param: str) -> None:
    """四个参数逐个有状态：**没写状态与「查过了没问题」在盘上长得一样**。"""
    entry = CALIBRATION_STATUS[param]

    assert isinstance(entry["calibrated"], bool)
    assert entry["date"], f"{param} 没写日期"
    assert entry["sample_size"] is not None, f"{param} 没写样本量"


@pytest.mark.parametrize("param", PARAMS)
def test_an_uncalibrated_param_says_why(param: str) -> None:
    """没标定的**必须说明为什么**——「待标定」三个字不是理由。"""
    entry = CALIBRATION_STATUS[param]
    if entry["calibrated"]:
        return
    assert len(entry["reason"]) >= 20, f"{param} 没写为什么标不了"
    assert entry["evidence"], f"{param} 没给证据出处"


def test_nothing_claims_to_be_calibrated_today() -> None:
    """本卡的结论：**今天一个参数都没标定**。

    这条是反向断言位——哪天真标定了一个，它会红，逼着改文档与状态表一起改。
    """
    claimed = [p for p, e in CALIBRATION_STATUS.items() if e["calibrated"]]

    assert claimed == [], f"这些参数自称已标定，但本卡没有标定过任何参数：{claimed}"


def test_the_uncalibrated_marker_is_still_on() -> None:
    """acceptance③的反面：既然没标定，**BL-05 的未标定标记就不许清除**。

    清除它等于宣称标定过了，而本卡的结论恰恰相反。
    """
    profile = load_tuning()

    assert profile.calibrated is False
    assert "初值" in profile.source


# ───────────────────────── 三、参数值一个没动（acceptance①的反面）


@pytest.mark.parametrize("module,name,value", [
    ("flint.retrieval.relevance", "THETA_REL", 0.6),
    ("flint.topic.differentiate", "_DELTA_FLOOR", 0.05),
    ("flint.topic.differentiate", "_DELTA_QUANTILE", 0.10),
])
def test_the_initial_values_are_untouched(module: str, name: str, value: float) -> None:
    """标不了就**不动**。改一个没有证据支持的值，比留着初值更糟：

    初值至少标着「未标定」，而改过的值看起来像是标定出来的。
    """
    import importlib

    assert getattr(importlib.import_module(module), name) == pytest.approx(value)


# ───────────────────────── 四、证据（acceptance①④）


def test_the_document_shows_the_before_after_table() -> None:
    """acceptance①：改前改后的对照要在文档里——**即使结论是「没改」**。"""
    doc = DOC.read_text(encoding="utf-8")

    assert "## 改前改后对照" in doc
    for param in ("theta_rel", "delta", "hotness"):
        assert param in doc, f"对照表里没有 {param}"


def test_the_delta_evidence_is_a_measurement_not_an_opinion() -> None:
    """δ 标不了这件事要有**实测数**撑着，不是一句「数据不好」。"""
    doc = DOC.read_text(encoding="utf-8")

    assert "1.0001" in doc, "没写任意两词距离均值（随机向量的特征）"
    assert "0.22" in doc or "0.2222" in doc, "没写扫出来的最优 F1"


def test_the_lineage_line_is_reported_against_the_s4_gate() -> None:
    """acceptance④：血缘对照 S4 的 ≥90%/50 簇，**达不到就照实说**。

    本卡的实测是「测得出 100%，但那批语料判不出错」——
    两句话都要在，只写前一句就是拿一个不能说明问题的数去对线。
    """
    lines = DOC.read_text(encoding="utf-8").splitlines()
    # 判据落在**血缘那一节里**：按全文判的话，「漂移」两个字在「下一步要什么」
    # 那张表里也有，把讲原因的那句删掉照样绿（变异考实测：23 条全过）。
    head = next(i for i, ln in enumerate(lines) if ln.startswith("## 血缘"))
    end = next((i for i, ln in enumerate(lines[head + 1:], head + 1)
                if ln.startswith("## ")), len(lines))
    section = "\n".join(lines[head:end])

    assert "≥90%" in section or "0.90" in section, "那一节没对 S4 的线"
    assert "60/60" in section, "那一节没写实测数"
    assert "漂移" in section, "没说清为什么这个 100% 不能拿来对线"


def test_the_goldsets_used_are_named_with_their_sizes() -> None:
    """用了哪批金标、多少条，要写出来——样本量是读这份结论的前提。"""
    doc = DOC.read_text(encoding="utf-8")
    counts = {
        kind: len((GOLDSETS / f"{kind}.jsonl").read_text(encoding="utf-8").splitlines())
        for kind in ("relevance", "same_topic", "lineage")
    }

    for kind, n in counts.items():
        assert f"{kind}" in doc and str(n) in doc, f"文档没写 {kind} 的条数（{n}）"


def test_the_caliber_and_the_status_cover_the_same_params() -> None:
    """口径表与状态表**同一批参数**：只在一边出现的参数，等于没人管它。"""
    assert set(CALIBRATION_CALIBER) == set(CALIBRATION_STATUS) == set(PARAMS)


def test_the_evidence_files_exist() -> None:
    """状态表里指的证据文件**真的在盘上**——指不到的证据等于没有证据。"""
    for param, entry in CALIBRATION_STATUS.items():
        for ref in entry["evidence"]:
            if ref.startswith(("docs/", "assets/")):
                assert (REPO / ref).exists(), f"{param} 的证据不在盘上：{ref}"


def test_the_status_table_is_machine_readable_json() -> None:
    """状态表能被序列化：下游要拿它做门，得先能读。"""
    assert json.loads(json.dumps(CALIBRATION_STATUS))
    assert hashlib.sha256(
        json.dumps(CALIBRATION_CALIBER, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest() == caliber_fingerprint()
