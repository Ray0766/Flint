"""K3-01：authority 权重调研定值——替掉 1.0 中性占位。

## 1.0 为什么该退场

K3 未决期间的口径是「唯一诚实的权重是 1.0」（`authority_axis.py` 原话）：
不替 owner 拍板。代价是这条轴**接了等于没接**——五档权威度打出来的分一模一样，
`authority_tier` 沦为一个记在 `components` 里没人用的字符串。

本卡不拿本项目的数据去拟合（金标集还不到位），而是**照公认方法论定初值**，
每条结论附出处，依据文档 `docs/authority权重-v041.md` 可复看。

## 初值是初值

权重标着 `calibrated=False` 与「来自方法论调研而非本项目实测」——
`AuthorityWeights` 的来源说明一路带到 `EvidenceScore.components`。
金标集到位后走既有调参通道（`flint/config.py#load_tuning`）标定，改配置不改代码。

## 判据最要紧的一条：改权重要真的改排序

一个算了不用的权重比没有更糟：它让人以为这条轴在起作用。
所以本文件有一组断言专门证明**「改权重 → 排序真的变」**。
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from flint.config import TUNING_KEYS, load_tuning
from flint.region.authority_axis import (
    AUTHORITY_BASIS,
    AuthorityWeights,
    apply_authority_axis,
    weight_for,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DOC = REPO_ROOT / "docs" / "authority权重-v041.md"
TIERS = ("official", "mainstream", "industry", "community", "unknown")


def _score(strength: int, **components: object) -> object:
    from flint.domain.models import EvidenceScore

    return EvidenceScore(strength=strength, axis="retrieved", components=dict(components))


# ───────────────────────── 一、依据文档可复看（acceptance①）


def test_the_basis_document_is_on_disk() -> None:
    assert DOC.exists(), "没有依据文档 = 权重是拍出来的"


def test_every_methodology_cited_carries_a_link() -> None:
    """acceptance①：**每条结论附出处链接**。

    没有链接的方法论与凭印象定的没有区别——下一个人无从复核，
    只能选择相信或者推倒重来。
    """
    lines = DOC.read_text(encoding="utf-8").splitlines()
    # 判据**限定在方法论那一节**：全文所有表格一起判的话，第二节的推导表
    # （那里本来就不该重复贴链接）会把断言判红，于是判据只能被放宽到没用。
    start = next(i for i, ln in enumerate(lines) if ln.startswith("## 一、"))
    end = next(i for i, ln in enumerate(lines[start + 1:], start + 1)
               if ln.startswith("## "))
    # 表头与数据行的分界**按分隔行定位**，不按行数偏移：`|---|---|` 不以 "| " 开头，
    # 于是「跳过前两行」实际跳掉的是表头 + **第一条数据行**——第一行方法论
    # 从此没人判（变异考实测：删掉它的链接，27 条全绿）。
    table = [ln for ln in lines[start:end] if ln.lstrip().startswith("|")]
    separator = next(i for i, ln in enumerate(table) if set(ln) <= set("| -:"))
    rows = table[separator + 1:]

    assert len(rows) >= 4, f"方法论那一节只有 {len(rows)} 行，卡面点了四个角度"
    assert [ln for ln in rows if "http" not in ln] == [], "方法论表里有不带出处的行"


def test_the_document_uses_no_hearsay_wording() -> None:
    """依据文档里 NEVER 出现「据了解」这类无出处表述（沿用 K1-01 的判据）。

    先剥掉「」引号里的内容——**引用一个禁用词正是禁掉它的方式**。
    """
    import re

    used = re.sub(r"「[^」]*」", "", DOC.read_text(encoding="utf-8"))

    for weasel in ("据了解", "据说", "业界共识", "众所周知", "一般认为"):
        assert weasel not in used, f"出现了无出处表述：{weasel}"


def test_the_document_covers_the_four_angles_the_card_names() -> None:
    """卡面点名的四个角度都要有交代：域名权重 / 同行评议 / 引用数 / 官方性。"""
    doc = DOC.read_text(encoding="utf-8")

    for angle in ("域名权重", "同行评议", "引用", "官方性"):
        assert angle in doc, f"依据文档没交代「{angle}」这个角度"


def test_every_tier_weight_is_derived_in_the_document() -> None:
    """五档的数**逐档写出怎么来的**，不是给一张结果表就完事。"""
    doc = DOC.read_text(encoding="utf-8")

    for tier in TIERS:
        lines = [ln for ln in doc.splitlines() if tier in ln and "→" in ln]
        assert lines, f"{tier} 的权重没写推导"


# ───────────────────────── 二、权重从配置读（acceptance②）


def test_the_weights_are_tunable_through_the_existing_channel() -> None:
    """acceptance②：**写进配置，NEVER 硬编码**。走既有调参通道，不另开一套。

    另开一套的后果：owner 要在两个地方调参，而两处里总有一处会被忘掉。
    """
    for tier in TIERS:
        assert f"authority.{tier}" in TUNING_KEYS, f"authority.{tier} 不在可调闭集里"


def test_a_config_override_actually_lands() -> None:
    """配置里给的值要真的顶掉初值——否则「可调」只是文档里的一句话。"""
    profile = load_tuning({"authority": {"official": 2.0}})

    assert profile.authority.official == 2.0
    assert profile.authority.mainstream == AuthorityWeights().mainstream
    assert "authority.official" in profile.overrides


def test_an_unknown_authority_key_is_rejected() -> None:
    """拼错的键要报错，NEVER 静默忽略：静默忽略会让 owner 以为自己调了参。"""
    from flint.config import TuningError

    with pytest.raises(TuningError):
        load_tuning({"authority": {"offical": 2.0}})


def test_the_initial_values_live_in_exactly_one_place() -> None:
    """初值只有一处（`AuthorityWeights` 的 dataclass 默认值）。

    这是既有调参通道的规矩：抄第二份就有了第二个真相，
    而两个真相里总有一个是旧的。
    """
    import inspect

    from flint import config

    code = inspect.getsource(config)

    for value in ("1.15", "0.77", "0.57"):
        assert value not in code, f"config.py 里抄了一份权重初值：{value}"


# ───────────────────────── 三、改权重要真的改排序（acceptance③）


def test_the_tier_changes_the_score() -> None:
    """同一份底分，官方源比社区源打出来的分**更高**——这是这条轴存在的意义。"""
    base = _score(60)

    official = apply_authority_axis(base, authority_tier="official")
    community = apply_authority_axis(base, authority_tier="community")

    assert official.strength > community.strength, (
        f"五档打出同一个分（{official.strength}）——轴接了等于没接")


def test_changing_the_weight_really_changes_the_order() -> None:
    """acceptance③：**改权重 → 排序真的变**，NEVER 让权重成为算了不用的摆设。

    构造一组：社区源底分高一点、官方源底分低一点。
    - 现行权重下：官方源被抬到前面；
    - 把官方权重压到 0.5：顺序**掉回来**。
    两次断言一起才算数——只测一次的话，「权重在起作用」与
    「恰好底分就是这个顺序」长得一模一样。
    """
    docs = [("hot_community", 62, "community"), ("gov_official", 55, "official")]

    def ranked(weights: AuthorityWeights) -> list[str]:
        scored = [
            (doc_id, apply_authority_axis(
                _score(strength), authority_tier=tier, weights=weights).strength)
            for doc_id, strength, tier in docs
        ]
        return [d for d, _ in sorted(scored, key=lambda p: -p[1])]

    assert ranked(AuthorityWeights()) == ["gov_official", "hot_community"]
    assert ranked(AuthorityWeights(official=0.5)) == ["hot_community", "gov_official"]


def test_the_five_tiers_are_strictly_ordered() -> None:
    """五档的权重**单调不增**：官方 ≥ 主流 ≥ 行业 ≥ 社区，unknown 不高于社区。

    次序乱了的话，产物上会出现「社区帖压过政府公告」这种排序，
    而读者无从知道是数据如此还是权重配反了。
    """
    w = AuthorityWeights()

    assert w.official > w.mainstream > w.industry >= w.community
    assert w.unknown <= w.community, "不知道来路的 NEVER 比已知最弱的更强"


def test_mainstream_is_the_anchor_at_one() -> None:
    """主流媒体档锚在 1.0：**改的是相对分量，不是整体分数水位**。

    五档全部 >1 的话，接轴会让所有分数一起涨，此前的金标结论要全部重跑。
    """
    assert AuthorityWeights().mainstream == 1.0


def test_an_unlisted_tier_falls_back_to_the_lowest() -> None:
    """认不出的档位按最低权重算，NEVER 按 1.0 放行。

    按 1.0 放行等于「拼错一个字符串就自动获得主流媒体的分量」。
    """
    w = AuthorityWeights()

    assert weight_for("offical", w) == min(w.community, w.unknown)


# ───────────────────────── 四、初值是初值（acceptance④）


def test_the_score_says_the_weight_is_not_calibrated_here() -> None:
    """acceptance④：产出里标注**来自方法论调研而非本项目实测**。"""
    scored = apply_authority_axis(_score(60), authority_tier="official")

    assert "方法论调研" in str(scored.components["authority_basis"])
    assert "本项目实测" in str(scored.components["authority_basis"])


def test_the_k3_placeholder_marker_is_gone() -> None:
    """acceptance②后半：`revisit(K3)` 标记随之移除——K3 已经有结论了。

    留着的话，下一个人会以为这仍是未决项，于是不敢用这条轴。
    """
    import inspect

    from flint.region import authority_axis

    code = inspect.getsource(authority_axis)

    assert "authority_revisit" not in code
    assert "K3" not in AUTHORITY_BASIS


def test_the_basis_note_points_at_the_document() -> None:
    """标注要指得到那份依据文档，不是一句空的「据调研」。"""
    assert "authority权重-v041" in AUTHORITY_BASIS


def test_calibration_is_still_pending_and_says_so() -> None:
    """没有配置时 `calibrated` 仍是 False——**方法论初值不等于标定过**。"""
    profile = load_tuning()

    assert profile.calibrated is False
    assert profile.authority == AuthorityWeights()


# ───────────────────────── 五、接轴的既有性质不许被这次改动带走


def test_original_components_are_still_preserved() -> None:
    """接轴仍然只**增**键，既有分量一个不改（否则质量卡口径就变了）。"""
    base = _score(60, verifiable=0.8, firsthand=0.9)

    scored = apply_authority_axis(base, authority_tier="official")

    for key, value in base.components.items():
        assert scored.components[key] == value
    assert set(scored.components) - set(base.components) == {
        "authority_tier", "authority_weight", "authority_basis"}


def test_applying_twice_does_not_compound() -> None:
    """重复接轴 NEVER 叠乘——叠乘会让同一份证据因为多走一遍流水线而变强。"""
    once = apply_authority_axis(_score(60), authority_tier="official")
    twice = apply_authority_axis(once, authority_tier="official")

    assert twice.strength == once.strength
    assert twice.components == once.components


def test_the_axis_field_still_keeps_dual_scale_semantics() -> None:
    """冻结件 `axis` 只有两值——authority NEVER 挤进这个字段。"""
    scored = apply_authority_axis(_score(60), authority_tier="unknown")

    assert scored.axis == "retrieved"


@pytest.mark.parametrize("tier", TIERS)
def test_no_tier_can_push_a_score_out_of_range(tier: str) -> None:
    """打完分仍在 0~100 内：`official` 那一档是 >1 的乘数，满分证据不能被顶出界。"""
    scored = apply_authority_axis(_score(100), authority_tier=tier)

    assert 0 <= scored.strength <= 100


def test_the_gate_and_the_axis_stay_separate() -> None:
    """门是布尔的、轴是连续的——本卡给 unknown 定了权重，**不等于放行 unknown**。

    REGION-03 的门照旧：仅 unknown 支撑时判 A/B 直接拒。
    两者混起来的话，一个权重值就悄悄改掉了判定门槛。
    """
    from flint.region.tier_gate import check_tier_gate

    gate = check_tier_gate(tiers=["unknown", "unknown"], proposed_verdict="A")

    assert gate.blocked is True
    assert apply_authority_axis(_score(60), authority_tier="unknown").strength > 0


def test_the_date_free_scoring_is_unaffected() -> None:
    """接轴不碰日期口径——这里只是把 K3 之前的 smoke 保住。"""
    scored = apply_authority_axis(_score(60, published_at=str(date(2026, 7, 1))),
                                  authority_tier="mainstream")

    assert scored.components["published_at"] == "2026-07-01"
    assert scored.strength == 60
