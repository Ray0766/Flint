"""JUDGE-05：全仓口径对齐总账——凡是判官判出来的数，都要有交代。

## 这张卡的产品是一张**不许漏项**的总账

一份「我检查过了」的清单，价值全在**它不可能漏掉东西**这件事上。
所以本文件的主判据不是「总账里写了什么」，而是**「盘上有的，总账里都有」**：
扫全仓找出所有带判官痕迹的产物，逐个要求它在总账里有一行。
新加一份跑批产物而忘了归类 → 直接红。

## 三类的边界

| 类 | 含义 | 处置 |
|---|---|---|
| `usable` | 口径自洽、判官一致（或**根本没有判官**：构造出来的金标、工具算出来的表） | 照用 |
| `rejudge` | 判官不同或口径已变，**但被判的东西还在**（组稿产物在盘上） | 用 DeepSeek 重判，新值落 `assets/deepseek_realign/` |
| `historical` | 题库/尺度/口径已变，或被判的东西已经不在 | **只能作历史**，且要说出为什么不可比 |

**「没有判官」也是一种自洽**：`goldcases.json` / `golddocs.json` 是 fixture 脚本
构造出来的**期望值**，不是谁判出来的——把它们塞进「需重判」是把构造真相
当成了判定结论。这条区分是本卡最容易做错的地方。

## 本卡 NEVER 改阈值

只对齐口径、产出对照。调线是 CAL-02 与 Z-01 的事——
本文件把四个现存阈值常量**逐个钉住**，本卡（或任何顺手的人）动了它就红。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
REALIGN = REPO / "assets" / "deepseek_realign"
INDEX = REALIGN / "index.json"
DOC = REPO / "docs" / "口径对齐总账-v041.md"

CLASSES = ("usable", "rejudge", "historical")

# 带判官痕迹的产物：JSON 里出现这些键之一就算「有判官判出来的数」。
JUDGE_MARKS = ("judge_model", "answered", "rate", "judged")


def _index() -> dict:
    return json.loads(INDEX.read_text(encoding="utf-8"))


def _entries() -> dict[str, dict]:
    return {e["path"]: e for e in _index()["entries"]}


def _artifacts_on_disk() -> set[str]:
    """盘上所有带判官痕迹的产物（相对仓根，正斜杠）。"""
    found: set[str] = set()
    for path in sorted((REPO / "assets").rglob("*.json")):
        if REALIGN in path.parents:
            continue  # 本卡自己的产物不进被审面
        raw = path.read_text(encoding="utf-8", errors="ignore")
        if not any(f'"{mark}"' in raw for mark in JUDGE_MARKS):
            continue
        # **那几个词出现，不等于它是判官产物。**
        #
        # `GAUGE-09` 实测撞上：`assets/gauge_map_b2.json` 里出现 `"rate"`，
        # 而它只是 `Z-01` 那条 acceptance 原文里被抽出来的一个**标识符**
        # （「任务一次通过率」那句里的 `rate=1.0`）。那份文件是尺子清点表，
        # 一个判官数都没有。
        #
        # 判「它是不是判官产物」而不是「有没有那个词」：
        # 判官产物的标志是那几个键出现在**键位**上（`"rate":`），
        # 而不是作为某个字符串的值躺在数组里。
        if not any(f'"{mark}":' in raw for mark in JUDGE_MARKS):
            continue
        found.add(path.relative_to(REPO).as_posix())
    return found


# ───────────────────────── 一、不许漏项（acceptance①）


def test_the_index_covers_every_artifact_on_disk() -> None:
    """**盘上有的，总账里都有**。这条是整张总账的价值所在。

    反过来判（「总账里写的都在盘上」）挡不住漏项：漏掉的那份恰恰不在总账里。
    """
    missing = sorted(_artifacts_on_disk() - set(_entries()))

    assert missing == [], f"这些产物没进总账：{missing}"


def test_the_index_lists_nothing_that_is_not_there() -> None:
    """反向：总账里不许有盘上没有的项——那种行会让人以为查过一个不存在的东西。"""
    ghosts = sorted(p for p in _entries() if not (REPO / p).exists())

    assert ghosts == []


def test_every_entry_has_a_class_from_the_closed_set() -> None:
    """三类是闭集。多出一类就意味着有人绕开了这三种处置。"""
    bad = {p: e.get("verdict") for p, e in _entries().items()
           if e.get("verdict") not in CLASSES}

    assert bad == {}, f"这些项的归类越界：{bad}"


def test_every_entry_says_who_judged_and_when() -> None:
    """acceptance④：判官是谁、什么时候判的、题库版本——三样都要有。

    允许写 `none`（没有判官的构造件）与 `unknown`（记录里没写），
    但**必须写出来**：空着与「记录里没写」在盘上长得一样，含义不同。
    """
    for path, entry in _entries().items():
        for field in ("judge", "judged_at", "bank_version"):
            assert str(entry.get(field) or "").strip(), f"{path} 缺 {field}"


def test_every_entry_states_comparability_with_a_reason() -> None:
    """**「不可比」要说出为什么不可比**——只写「不可比」等于没写。"""
    for path, entry in _entries().items():
        assert isinstance(entry.get("comparable"), bool), f"{path} 没写可不可比"
        if not entry["comparable"]:
            assert len(str(entry.get("why_not") or "")) >= 15, (
                f"{path} 说不可比却没说为什么")


# ───────────────────────── 二、三类各自的处置（acceptance②③）


def test_every_rejudge_entry_has_a_new_artifact() -> None:
    """acceptance③：判为「需重判」的，**必须真的重判过**。

    没有新产物的「需重判」是一句待办，不是一次对齐。
    """
    for path, entry in _entries().items():
        if entry["verdict"] != "rejudge":
            continue
        target = REPO / str(entry.get("realigned_to") or "")
        assert target.exists(), f"{path} 判为需重判，却没有新产物"
        payload = json.loads(target.read_text(encoding="utf-8"))
        assert payload["judge_model"], f"{target.name} 没记新判官"
        assert payload["judged"] > 0


NEW_VALUE_DIRS = ("assets/deepseek_realign/", "assets/prod_caliber/deepseek_judge/")


def test_the_new_artifacts_never_overwrite_the_old_ones() -> None:
    """acceptance③：旧值**原样保留**——新值只落在两个「新值目录」之一。

    两个而不是一个：JUDGE-03 已经把三份重判进了 `deepseek_judge/`，
    再往 `deepseek_realign/` 抄一份就有了第二份真相。**指过去，不是复制过去。**
    """
    for path, entry in _entries().items():
        target = entry.get("realigned_to")
        if not target:
            continue
        assert target != path, f"{path} 的新值指向了它自己"
        assert target.startswith(NEW_VALUE_DIRS), f"新值落到了旧目录：{target}"


def test_a_historical_entry_never_pretends_to_be_comparable() -> None:
    """判为「只能作历史」的，`comparable` 必须是 False——否则这个分类没有意义。"""
    for path, entry in _entries().items():
        if entry["verdict"] == "historical":
            assert entry["comparable"] is False, f"{path} 判为历史却标了可比"


def test_a_usable_entry_explains_why_it_is_still_usable() -> None:
    """判为「还能用」的要给理由：**「没有判官」也是一种理由**，但要写出来。

    不写的话，「查过了没问题」与「没查」在总账上长得一模一样。
    """
    for path, entry in _entries().items():
        if entry["verdict"] == "usable":
            assert len(str(entry.get("note") or "")) >= 10, f"{path} 没写为什么还能用"


def test_the_constructed_goldsets_are_not_called_judge_output() -> None:
    """**构造件不是判定结论**：金标是 fixture 脚本生成的期望值，不是谁判出来的。

    把它们归进「需重判」，就是把构造真相当成了判定结论去重判一遍——
    重判出来的东西会顶掉本来当基准用的那份。
    """
    for name in ("assets/goldcases/goldcases.json", "assets/golddocs/golddocs.json"):
        entry = _entries()[name]
        assert entry["verdict"] == "usable"
        assert entry["judge"] == "none"


def test_byte_identical_duplicates_are_marked_as_such() -> None:
    """内容逐字节相同的重复件要标出来——**重判两遍是白花一次钱**。"""
    dupes = [p for p, e in _entries().items() if e.get("duplicate_of")]

    assert dupes, "一份重复件都没标出来（盘上有 backup / 变体同源的情况）"
    for path in dupes:
        origin = _entries()[path]["duplicate_of"]
        assert origin in _entries(), f"{path} 指向的原件不在总账里"


# ───────────────────────── 三、文档（acceptance②④）


def test_the_document_has_one_section_per_class() -> None:
    """三类各一节：混在一张表里的话，「还能用」与「只能作历史」会被一起读成结论。"""
    doc = DOC.read_text(encoding="utf-8")

    for title in ("## 还能用", "## 需重判", "## 只能作历史"):
        assert title in doc, f"总账缺一节：{title}"


def test_the_document_lists_every_entry() -> None:
    """文档里逐项列出——机读的 index 是给程序看的，文档是给人看的，两者都要全。"""
    doc = DOC.read_text(encoding="utf-8")
    missing = [p for p in _entries() if p not in doc]

    assert missing == [], f"文档里漏了：{missing}"


def test_the_document_and_the_index_agree_on_the_counts() -> None:
    """两处的条数要对得上——对不上时，读文档的人与跑程序的人会得到两个结论。"""
    import re

    doc = DOC.read_text(encoding="utf-8")
    counts = {v: sum(1 for e in _entries().values() if e["verdict"] == v) for v in CLASSES}

    for verdict, n in counts.items():
        stated = re.findall(rf"{verdict}=(\d+)", doc)
        assert stated, f"文档没写 {verdict} 的条数（应为 {n}）"
        # **每一处都要对**：文档里写了两遍（摘要一次、小节标题一次），
        # 只判「有一处对」的话，改掉其中一处不会红——而两处互相矛盾
        # 比只写一处更糟（变异考实测：改摘要那处，18 条全过）。
        wrong = [s for s in stated if int(s) != n]
        assert wrong == [], f"{verdict} 的条数有 {len(stated)} 处，其中 {wrong} 与机读面不符（应为 {n}）"


# ───────────────────────── 四、本卡 NEVER 改阈值（acceptance⑤）


@pytest.mark.parametrize("module,name,value", [
    ("eval.doc_metrics", "CHECK_ANSWER_LINE", 0.90),
    ("flint.retrieval.relevance", "THETA_REL", 0.6),
    ("flint.config", "Z_LINE_INITIAL", 0.95),
    ("harness.lineage_accuracy", "EXIT_LINE", 0.90),
])
def test_no_threshold_moved(module: str, name: str, value: float) -> None:
    """四个现存阈值逐个钉住。**调线是 CAL-02 与 Z-01 的事**，不是本卡的。

    钉在这里而不是「本卡没改过文件」上：后者对「别的卡顺手改了」无感，
    而这条对谁改的都一样红。
    """
    import importlib

    assert getattr(importlib.import_module(module), name) == pytest.approx(value)
