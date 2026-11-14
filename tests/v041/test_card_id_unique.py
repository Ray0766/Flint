"""FIX-14：卡号跨批次唯一——以及撞车之后**该怎么办**。

## 单子记的是一张，实际是四张

`docs/blocked/CARD-ID-COLLISION-DESIGN-01.md` 只点了 `DESIGN-01`。
本卡开工第一件事是把全部任务表并起来数，扫出**四张**：

| 卡号 | v0.4 那张是什么 | v0.4.1 那张是什么 |
|---|---|---|
| `DESIGN-01` | 对话面板 + SSE 流式渲染 | `design_generate` 的消费者 |
| `DESIGN-02` | 渲染管线 `iframe.srcdoc` | 设计台那一屏（输入/流式/预览） |
| `DESIGN-03` | 三接口抽象 | 固化为模板 + 第四态 |
| `REGION-08` | `by_source` 跨国分列 | `clusters` 加 region 列（迁移 0021） |

**两侧的 outputs 完全不同**，而 `check_outputs_declared.py` 按模块 docstring
首行的卡号去查 outputs——已经据此误判过一次。

## 处置：**一个号都不改**，理由在这里

卡面写的是「改新的那张更安全——旧卡已 verified」。**那句话开工时是对的，
现在不成立了**：`DESIGN-01/02/03` 是第 5 批的卡、`REGION-08` 是本批的卡，
四张**新的也全部 verified 了**。

改任何一侧的号，代价是同一种：

- `docs/progress-v041.jsonl` 是 **append-only**，里面那些 `started`/`verified`
  事件会指向一个不存在的卡号——而**指错的引用与指对的长得一模一样**；
- 台账配对尺子会当场把它们报成「未配对事件」，
  而那句话读起来像「有张卡被丢了」；
- `docs/trace/REGION-09.md`、`docs/trace/REGION-10.md` 里逐字引着 `REGION-08`。

**所以改号现在是有害的**，本卡改的是**别的两样**：

1. 一条跨批次唯一性判据，让**下一次**撞车当场被抓；
2. `check_outputs_declared.py` 在卡号有歧义时**报错**，NEVER 静默挑一张。

第 2 条才是那次误判的直接修法——它把这四张撞车的实际危害清零。
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

TASK_FILES = [REPO / "tasks-v04.json", *sorted(
    (REPO / "docs" / "steward").glob("tasks-*.json"))]
SHEET = REPO / "docs" / "blocked" / "CARD-ID-COLLISION-DESIGN-01.md"

# 已发生且**现在改不动**的撞车（首次机械审计 @2026-08-09 采集，冻结闭集）。
# 每条写明两侧各是什么——**NEVER 增补**：新的撞车应当被抓红而非入册。
#
# 为什么改不动：两侧都已 verified，而台账 append-only。改任何一侧的号，
# 那些 `started`/`verified` 事件都会指向一个不存在的卡号。
LEGACY_COLLISIONS: dict[str, str] = {
    "DESIGN-01": "v04：对话面板 + SSE 流式渲染 / b5：design_generate 的消费者",
    "DESIGN-02": "v04：渲染管线 iframe.srcdoc / b5：设计台那一屏",
    "DESIGN-03": "v04：三接口抽象 / b5：固化为模板 + 第四态",
    "REGION-08": "v04：by_source 跨国分列 / b6：clusters 加 region 列（迁移 0021）",
}


def _tasks(path: Path) -> list[dict[str, object]]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return list(data["tasks"] if isinstance(data, dict) and "tasks" in data else data)


def _by_id() -> dict[str, list[str]]:
    seen: dict[str, list[str]] = defaultdict(list)
    for path in TASK_FILES:
        if not path.exists():
            continue
        for task in _tasks(path):
            seen[str(task["id"])].append(path.name)
    return dict(seen)


# ───────────────────────── 一、跨批次唯一性


def test_the_task_files_are_all_readable() -> None:
    """先确认扫描面是全的——**扫不到的文件不算干净**。

    少读一份任务表的话，这条判据会因为「没看见」而绿，
    而那与「真的没有撞车」长得一模一样。
    """
    found = [p.name for p in TASK_FILES if p.exists()]

    assert len(found) >= 6, f"任务表只扫到 {found}——扫描面塌了"
    for path in TASK_FILES:
        if path.exists():
            assert _tasks(path), f"{path.name} 解析出零张卡"


def test_no_new_card_id_collides_across_batches() -> None:
    """**这一条是本卡真正留下来的东西**：下一次撞车当场被抓。

    冻结闭集之外出现任何重复即红，并点名两处出处——
    只说「有重复」的话，人还要自己去四份任务表里找。
    """
    offenders = {
        card: files for card, files in _by_id().items()
        if len(files) > 1 and card not in LEGACY_COLLISIONS
    }

    assert offenders == {}, (
        "卡号跨批次撞车：\n"
        + "\n".join(f"  {card} → {files}" for card, files in sorted(offenders.items()))
    )


def test_the_legacy_set_is_exactly_what_is_on_disk() -> None:
    """冻结闭集**逐条对得上实况**：既不多也不少。

    多一条 = 有人把已经解决的撞车留在名单里，下一次它会替一次真撞车打掩护；
    少一条 = 上面那条判据会红，而红的是一件**现在改不动**的事。
    """
    on_disk = {card for card, files in _by_id().items() if len(files) > 1}

    assert on_disk == set(LEGACY_COLLISIONS), (
        f"名单与实况对不上：多出 {sorted(set(LEGACY_COLLISIONS) - on_disk)}，"
        f"少了 {sorted(on_disk - set(LEGACY_COLLISIONS))}"
    )


def test_every_legacy_entry_says_what_the_two_sides_are() -> None:
    """每条撞车写明**两侧各是什么**。

    只记一个卡号的话，下一个人得自己去两份任务表里对，
    而那正是这张单子拖到现在才被数清的原因（单子只点了一张，实际四张）。
    """
    for card, note in LEGACY_COLLISIONS.items():
        assert "/" in note, f"{card} 没写清两侧：{note}"
        assert len(note) > 20, f"{card} 的说明太短：{note}"


def test_the_ruler_would_catch_a_fresh_collision() -> None:
    """**阴性对照**：注入一张重号的卡，必须抓到。

    没有这一条，把 `_by_id` 写坏（比如只读一份表）也能让全仓绿。
    """
    seen = dict(_by_id())
    seen["FAKE-99"] = ["tasks-a.json", "tasks-b.json"]

    offenders = {
        card: files for card, files in seen.items()
        if len(files) > 1 and card not in LEGACY_COLLISIONS
    }

    assert offenders == {"FAKE-99": ["tasks-a.json", "tasks-b.json"]}


# ───────────────────────── 二、歧义时报错，NEVER 静默挑一张


def test_the_outputs_checker_refuses_an_ambiguous_card_id() -> None:
    """`check_outputs_declared.py` 撞见有歧义的卡号时**抛**。

    静默挑第一张的后果就是那次误判：一个 v0.4.1 的模块被拿去与
    v0.4 那张同号卡的 outputs 比，然后被报成「少声明了一个产物」——
    **而那句话是假的**，它在自己那张卡上写得清清楚楚。
    """
    from tools.check_outputs_declared import AmbiguousCardId, resolve_card

    with pytest.raises(AmbiguousCardId, match="DESIGN-01"):
        resolve_card("DESIGN-01", {"DESIGN-01": ["tasks-v04.json", "b5.json"]})


def test_an_unambiguous_card_id_resolves_normally() -> None:
    """**阴性对照**：没有歧义时照常返回，NEVER 一律抛。

    一律抛的话，这把尺子对整个仓库都不能用了——
    「更严格」与「不能用」是两件事。
    """
    from tools.check_outputs_declared import resolve_card

    assert resolve_card("SLOT-01", {"SLOT-01": ["tasks-v041-b6.json"]}) == (
        "tasks-v041-b6.json")
    # **不在任何表里回 None，NEVER 抛**：那不是歧义，是「这个卡号没有卡」——
    # 那件事由 C 类自己去报（它报得更准，还会带上是哪个文件自述的）。
    # 在这里抛的话，一次「卡号打错了」会以 KeyError 收场，读起来像尺子崩了。
    assert resolve_card("NOPE-99", {}) is None


def test_the_checker_still_runs_clean_on_this_repo() -> None:
    """加了那道拒绝之后，尺子对本仓仍然跑得通。

    四张撞车都在冻结闭集里，而它们的 outputs 面**没有交集**——
    所以本仓今天不会触发那道拒绝。哪天触发了，那是真出事了。
    """
    import subprocess

    done = subprocess.run(
        [sys.executable, str(REPO / "tools" / "check_outputs_declared.py")],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=REPO, check=False)

    assert done.returncode == 0, done.stdout[-2000:] + done.stderr[-2000:]


# ───────────────────────── 三、处置写下来了


def test_the_sheet_records_that_nothing_was_renamed_and_why() -> None:
    """卡面写的处置是「改新的那张」。**开工后发现那句话不再成立**——
    四张新的也全部 verified 了，改号会让 append-only 台账里的事件指向空处。

    单子里 MUST 写清：改了没有、为什么、以及**真正的修法是哪两条**。
    """
    text = SHEET.read_text(encoding="utf-8")
    state = next(ln for ln in text.splitlines()[:8] if ln.startswith("**状态**"))

    assert state.startswith("**状态** closed"), f"单据还开着：{state!r}"
    assert "FIX-14" in text
    for must in ("四", "append-only", "AmbiguousCardId"):
        assert must in text, f"单子里没写 {must}"
    for card in LEGACY_COLLISIONS:
        assert card in text, f"单子里没点名 {card}——它只记了一张，而实际有四张"
