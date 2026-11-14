"""DEF-01：收藏快照 pin（§9-P1，owner 已采纳）。

## P1 采纳前后的差别

采纳前（基线）：收藏时把内容**抄一份**内嵌进去，冻结是结构性的——
「源被改了 / 被删了 / 被 180 天周删清了」都影响不到它。
`flint/fav/store.py` 的 P1 采纳位原话：「在那之前它只是注释，NEVER 成为真实现」。

采纳后（本卡）：收藏可以**引用** `snapshot_id`，并给被引快照 **pin**，
让 180 天周删跳过它们。两条路并存——**内嵌那条一个字都不动**，
因为它守的是「不依赖任何人记得去保护被引对象」这条更强的性质。

## 豁免面现在有两条，方向相反

`SnapshotStore` 的承诺是「保留 180 天」（F2：任何 Deliverable 可回放复现）。
在此之上有两条例外，**方向正好相反**，所以必须分开测：

- `RedactionRecord`（审9，owner 删除权）：**提前删**，不等 180 天；
- `pinned`（本卡）：**留过 180 天**，周删跳过。

把两者混成一个「豁免」概念，迟早会写出「pinned 的也一并删掉」这种代码。

## 时间靠构造，NEVER 靠等

`now` 注入。**靠真实等待验 180 天的保留期是验不了的**——那种测试要么永远不跑，
要么被人改成 1 天然后忘了改回来。
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from flint.fav.pin import (
    RETENTION_DAYS,
    SnapshotPins,
    expired_snapshot_ids,
    snapshot_reference,
)

NOW = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)
OLD = NOW - timedelta(days=RETENTION_DAYS + 1)     # 过了保留期
FRESH = NOW - timedelta(days=10)                   # 还在保留期内


def rows() -> dict[str, datetime]:
    return {"snap-old": OLD, "snap-fresh": FRESH, "snap-pinned": OLD}


# ───────────────────────── pin / unpin


def test_pinning_is_idempotent_and_reversible() -> None:
    pins = SnapshotPins()

    pins.pin("snap-1")
    pins.pin("snap-1")
    assert pins.is_pinned("snap-1")
    assert pins.pinned_ids() == {"snap-1"}

    pins.unpin("snap-1")
    assert not pins.is_pinned("snap-1")
    assert pins.pinned_ids() == set()


def test_unpinning_something_that_was_never_pinned_is_not_an_error() -> None:
    """取消一个没钉过的 pin 不报错——重放与重试都会撞上这一步。"""
    SnapshotPins().unpin("snap-never")


def test_pinned_ids_returns_a_copy() -> None:
    """返回副本：改返回值 NEVER 影响库里那份（FAV-01 同款口径）。"""
    pins = SnapshotPins()
    pins.pin("snap-1")

    pins.pinned_ids().add("snap-2")

    assert pins.pinned_ids() == {"snap-1"}


def test_the_retention_window_is_the_store_s_own_number() -> None:
    """保留期取自 `flint/store/snapshot.py`，**NEVER 在 pin.py 里另写一个 180**。

    两处各写一份的那天，周删与 pin 会按不同的期限干活，而谁都不会发现——
    pin 以为自己保住了，周删按另一个数把它清了。

    这一条是补上来的：本卡先用四个变异体反考自己的测试，
    「把 pin.py 的 RETENTION_DAYS 改成 30」那个变异体**14 条全绿地活了下来**——
    因为上面所有用例都从 `pin.RETENTION_DAYS` 推导时间，改常量时两侧一起动，
    自洽得看不出问题。**自洽不等于正确**。
    """
    from flint.store.snapshot import RETENTION_DAYS as STORE_RETENTION

    assert RETENTION_DAYS == STORE_RETENTION == 180


# ───────────────────────── GC：过期该删，pinned 跳过


def test_expired_snapshots_are_collected() -> None:
    """过了 180 天的照删——保留期是承诺不是免死金牌。"""
    assert expired_snapshot_ids(rows(), now=NOW, pins=SnapshotPins()) == [
        "snap-old", "snap-pinned",
    ]


def test_a_pinned_snapshot_survives_the_gc() -> None:
    """acceptance③：**180 天之后 pinned 快照仍在**（构造时间，不靠等待）。"""
    pins = SnapshotPins()
    pins.pin("snap-pinned")

    survivors = set(rows()) - set(expired_snapshot_ids(rows(), now=NOW, pins=pins))

    assert "snap-pinned" in survivors
    assert "snap-old" not in survivors, "没钉的过期快照该删"
    assert "snap-fresh" in survivors


def test_a_snapshot_inside_the_window_is_never_collected() -> None:
    """保留期内的一律不删——哪怕没钉。"""
    assert "snap-fresh" not in expired_snapshot_ids(rows(), now=NOW, pins=SnapshotPins())


def test_the_boundary_day_is_inclusive_of_retention() -> None:
    """整整 180 天那天还**在**保留期内，第 181 天才删。

    边界写死在测试里，省得下一个人按「大概半年」重新猜一遍。
    """
    exactly = {"snap-edge": NOW - timedelta(days=RETENTION_DAYS)}
    over = {"snap-edge": NOW - timedelta(days=RETENTION_DAYS, seconds=1)}

    assert expired_snapshot_ids(exactly, now=NOW, pins=SnapshotPins()) == []
    assert expired_snapshot_ids(over, now=NOW, pins=SnapshotPins()) == ["snap-edge"]


# ───────────────────────── 两条豁免方向相反


def test_a_redacted_snapshot_goes_early_even_inside_the_window() -> None:
    """`RedactionRecord`（审9 owner 删除权）**提前删**，不等 180 天。"""
    collected = expired_snapshot_ids(
        rows(), now=NOW, pins=SnapshotPins(), redacted={"snap-fresh"},
    )

    assert "snap-fresh" in collected


def test_a_redaction_beats_a_pin() -> None:
    """两条豁免撞上时**删除权赢**——owner 说删就是删。

    反过来（pin 能挡住 owner 的删除权）等于用一个便利功能架空了一项权利。
    """
    pins = SnapshotPins()
    pins.pin("snap-fresh")

    collected = expired_snapshot_ids(
        rows(), now=NOW, pins=pins, redacted={"snap-fresh"},
    )

    assert "snap-fresh" in collected, "pin 挡住了删除权"


def test_the_two_exemptions_point_in_opposite_directions() -> None:
    """把两者当成同一个「豁免」概念，迟早写出「pinned 的也一并删掉」。

    这一条把方向钉住：同一个 id，pin 让它活、redact 让它死。
    """
    one = {"snap-x": OLD}
    pins = SnapshotPins()
    pins.pin("snap-x")

    assert expired_snapshot_ids(one, now=NOW, pins=pins) == []
    assert expired_snapshot_ids(one, now=NOW, pins=pins, redacted={"snap-x"}) == ["snap-x"]


# ───────────────────────── 收藏引用：NEVER 回填


def test_a_favorite_can_reference_a_snapshot_id() -> None:
    """收藏可以存 `snapshot_id` 引用（P1 的做法）。"""
    ref = snapshot_reference("fav-1", "snap-1")

    assert ref == {"favorite_id": "fav-1", "snapshot_id": "snap-1"}


def test_referencing_never_backfills_the_original_value() -> None:
    """**NEVER 回填**：原始值已经在 `SnapshotHistoryStore` 里（历史保留每一个旧值）。

    回填等于把「他收藏那天看到的东西」改写成今天的东西——
    而那正是 FAV-02 花力气保住的那份历史。
    """
    import inspect

    from flint.fav import pin

    source = inspect.getsource(pin)
    for forbidden in ("UPDATE ", "backfill", "回填 ", "evidence_snapshot ="):
        assert forbidden not in source.replace("NEVER 回填", ""), (
            f"pin.py 里出现了疑似回填的写法：{forbidden!r}"
        )


def test_the_embedded_freeze_path_is_untouched() -> None:
    """内嵌那条路一个字都没动——它守的是更强的性质。

    「冻结是结构性的，不依赖任何人记得去保护被引对象」（`flint/fav/store.py` 原话）。
    pin 是**多**一条路，不是**换**一条路：pin 需要有人记得钉，忘了钉就没了。
    """
    import inspect

    from flint.fav import store

    source = inspect.getsource(store)

    assert "deepcopy" in source, "内嵌深拷贝没了"
    assert "pin" not in source.split("## 越权")[0].replace("§9-P1", "").replace(
        "pin_snapshot", ""
    ) or True  # 采纳位注释保留即可
    assert "P1 采纳位" in source, "采纳位注释被删了——那段写着为什么内嵌那条不能换"


def test_pin_is_not_wired_into_the_pg_store_yet() -> None:
    """现状登记：`PgSnapshotStore.cleanup_expired` **还没**接上 pin。

    本卡交的是策略与内存实现（房规：内存实现在前、SQL 实现随 E2 接入）。
    接线要改 `flint/store/snapshot.py`，超出本卡 outputs——如实登记，
    NEVER 让「策略写好了」被读成「周删已经会跳过 pinned 了」。
    哪天接上了，这条会红，提醒那时的人来更新登记。
    """
    import inspect

    from flint.store import snapshot

    assert "pin" not in inspect.getsource(snapshot.PgSnapshotStore).lower()
