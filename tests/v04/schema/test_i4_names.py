"""SCHEMA-05 验收：I4 名称三元组落 `Cluster`（native 权威 + display 派生）。

acceptance（tasks-v04.json#SCHEMA-05）：
  ① name_native 写后读回字节等同（frozen 拒二次赋值）；
  ② name_display 槽为 TranslatedText 判别。

## acceptance ① 的「frozen」与真件冲突 —— 按 §1.4 处理

真件 `Cluster` 是**非 frozen** 的 `@dataclass`（`docs/schema_reconcile_prefill_v04.md` 注记 2
已核实），`WORKORDER-v04.md#3-B7`「违反时」也已改成
「写路径校验拒绝对 name_native 的改写（真件为非 frozen dataclass，权威性由校验与测试保证）」。
把整个 `Cluster` 改 frozen 会改变既有字段的可变性语义（越界，且与 contracts/ 冲突）。

本卡按 **contracts/ + §3-B7** 实现：**字段级写一次**——`name_native` 允许构造，
拒绝二次赋值；其余字段的可变性不动。冲突已登记 `docs/blocked/SCHEMA-05-FROZEN-WORDING.md`。

## 为什么「字节等同」值得单独测

B7 的失守方式不是「有人手动改名」，而是**入库时顺手归一化**：全角转半角、
去空白、大小写折叠、Unicode NFC/NFKC。这些都「看起来没改内容」，
但 embedding 与去重吃的是字节——一次归一化就让同一个热点在两天里变成两个簇。
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
V04 = REPO_ROOT / "contracts_v04" / "models_v04.py"


def _load() -> object:
    spec = importlib.util.spec_from_file_location("models_v04", V04)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["models_v04"] = module
    spec.loader.exec_module(module)
    return module


M = _load()

# 三种最容易被「顺手归一化」掉的真实原文
NATIVE_SAMPLES = [
    "全固体電池の量産",            # 日文
    "ＡＩ　半導体",                # 全角字母与全角空格
    "K-배터리  수출",              # 韩文 + 连续空格
]


def _cluster(name_native: str) -> object:
    return M.Cluster(
        cluster_id="c1", canonical_name="固态电池", category_id="cat-ai",
        centroid=[0.0], status="active", first_seen=date(2026, 8, 1),
        last_active=date(2026, 8, 2), parent_cluster_ids=[], merged_into=None,
        aliases=[], name_native=name_native, name_lang="ja", name_display=None)


@pytest.mark.parametrize("native", NATIVE_SAMPLES)
def test_name_native_round_trips_byte_for_byte(native: str) -> None:
    """写后读回**字节**等同——NEVER 有任何归一化。"""
    c = _cluster(native)
    assert c.name_native == native
    assert c.name_native.encode("utf-8") == native.encode("utf-8"), "name_native 被归一化了"


@pytest.mark.parametrize("native", NATIVE_SAMPLES)
def test_name_native_rejects_second_assignment(native: str) -> None:
    """写一次即定：二次赋值被拒（§3-B7「写路径校验拒绝对 name_native 的改写」）。"""
    c = _cluster(native)
    with pytest.raises(AttributeError, match="name_native"):
        c.name_native = "改写后的名字"
    assert c.name_native == native, "拒绝之后原值 MUST 保持不变"


def test_other_fields_stay_mutable() -> None:
    """只钉 name_native 这一个字段——把整个 Cluster 改 frozen 会越界改既有语义。"""
    c = _cluster("全固体電池")
    c.last_active = date(2026, 8, 3)
    c.aliases = ["固态电池"]
    assert c.last_active == date(2026, 8, 3)
    assert c.aliases == ["固态电池"]


def test_canonical_name_is_preserved_alongside_native() -> None:
    """预填表：`canonical_name` 保留，与 name_native 的关系由 REGION-04 命名规则成文。"""
    fields = set(M.Cluster.__dataclass_fields__)
    assert {"canonical_name", "name_native", "name_lang", "name_display"} <= fields


def test_name_display_slot_is_translated_text_keyed_by_language() -> None:
    """acceptance ②：display 槽是 TranslatedText 判别，且键为 SystemLanguage。"""
    ann = str(M.Cluster.__dataclass_fields__["name_display"].type)
    assert "SystemLanguage" in ann and "TranslatedText" in ann, ann

    display = {"en": M.TranslatedText(
        text="All-solid-state battery", translated=True,
        translator="qwen3.6:35b-a3b@v2", source_field="name_native")}
    c = M.Cluster(
        cluster_id="c2", canonical_name="固态电池", category_id="cat-ai",
        centroid=[0.0], status="active", first_seen=date(2026, 8, 1),
        last_active=date(2026, 8, 2), parent_cluster_ids=[], merged_into=None,
        aliases=[], name_native="全固体電池", name_lang="ja", name_display=display)
    assert c.name_display["en"].translated is True
    assert c.name_display["en"].source_field == "name_native", "译文 MUST 指回它派生自的原文字段"
