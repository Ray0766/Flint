"""BL-05：热点参数标定通道（阈值出配置、跑批器可 A/B、**恒 report_only**）。

## 通道要解决的是「谁也不敢动那些数」

`HotnessConfig` 的 G/α/β/γ/ν、`BurstConfig` 的 s/γ、`WeakSignalConfig` 的
agg_ceiling/drift_penalty/burst_coef、`THETA_REL`、δ——十几个数散在四个模块里，
**每一个都是 S4 的未决项**（「待金标集调参」）。想调，今天只能改代码；
改了代码就分不清「这版是标定过的」还是「谁顺手改的」。

本卡建的是**通道**，不是结论：

- 参数**从配置读**，配置缺失就用代码里那份初值，并在输出里标 **未标定**；
- 跑批器能对**同一批数据**跑两组参数出对照表；
- **恒 report_only**：本卡 NEVER 改任何默认值——调参是 owner 决策（S4）。

## 「未标定」必须看得见

配置缺失时结果照样能出，但它与标定过的结果**长得必须不一样**。
一模一样的那天，一份没标定的排序会被当成调参结论用下去。

## 本卡不碰那三个模块

`flint/hotness.py` / `burst.py` / `weaksignal.py` 在卡面里是 **inputs 不是 outputs**：
初值就住在它们的 dataclass 默认值里，那是**唯一一处**初值（acceptance③ 的
「配置缺失时用当前初值」指的正是它们）。通道只负责**读配置覆盖它们**，
NEVER 在别处再抄一份数——抄一份就有了第二个真相。
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from flint.burst import BurstConfig
from flint.config import (
    TUNING_KEYS,
    TuningProfile,
    load_tuning,
    tuning_note,
)
from flint.hotness import ClusterSeries, HotnessConfig, rank_hotness
from flint.weaksignal import WeakSignalConfig

REPO_ROOT = Path(__file__).resolve().parents[2]


TODAY = date(2026, 7, 20)


def _series(cluster_id: str, agg: float, series: list[float]) -> ClusterSeries:
    """按日序列铺到 `TODAY` 为止（最后一天 = 序列末值）。"""
    days = [TODAY - timedelta(days=len(series) - 1 - i) for i in range(len(series))]
    return ClusterSeries(
        cluster_id=cluster_id,
        first_seen=date(2026, 7, 1),
        agg_by_day=dict(zip(days, series, strict=True)),
        by_source_today={"gtrends": agg},
    )


# ───────────────────────── 通道：读得到、缺了也能跑


def test_an_empty_config_falls_back_to_the_code_defaults() -> None:
    """acceptance③：配置缺失 → 用当前初值，且**标未标定**。"""
    profile = load_tuning(None)

    assert profile.hotness == HotnessConfig()
    assert profile.burst == BurstConfig()
    assert profile.weak_signal == WeakSignalConfig()
    assert profile.calibrated is False


def test_the_uncalibrated_profile_says_so_in_words() -> None:
    """未标定要**成句写出来**：字段要人去查，句子会被读到。

    一份没标定的排序被当成调参结论用下去，是这条通道最该防的事。
    """
    note = tuning_note(load_tuning(None))

    assert "未标定" in note
    assert "report_only" in note


def _full_config() -> dict[str, object]:
    """把每一个旋钮都写上（全标定）。"""
    payload: dict[str, object] = {}
    for key in TUNING_KEYS:
        group, _, leaf = key.rpartition(".")
        if group:
            payload.setdefault(group, {})
            payload[group][leaf] = 1.0      # type: ignore[index]
        else:
            payload[key] = 1.0
    return payload


def test_a_fully_calibrated_profile_does_not_cry_wolf() -> None:
    """阴性对照：**每个**旋钮都来自配置时，那句话不出现——否则它会被读成噪音。"""
    note = tuning_note(load_tuning(_full_config()))

    assert "未标定" not in note


def test_a_partly_calibrated_profile_names_what_is_still_a_default() -> None:
    """只调了一个旋钮时，**其余仍是初值**这件事必须写在同一行里。

    「已标定」是个整体印象，而真相往往是「G 标了，θ_rel 没标」——
    不写出来，那些没标的会被一起算成标过的。
    """
    note = tuning_note(load_tuning({"hotness": {"gravity": 1.8}}))

    assert "来自配置：hotness.gravity" in note
    assert "仍是初值（未标定）" in note
    assert "theta_rel" in note


def test_every_documented_knob_is_reachable_from_the_config() -> None:
    """acceptance①：卡面点名的**每一个**旋钮都在通道里。

    少一个就意味着那个数只能改代码——而改代码分不清标定与顺手改。

    判的是**包含**不是相等：这条通道本来就是给后续参数报到用的
    （`TUNING_KEYS` 上方原话「加一个数进来就要在这里报到」），
    判相等会让每次加旋钮都撞红一条与它无关的断言。
    K3-01 就是这么加进来的五个 `authority.*`。
    **新加的旋钮跑不掉**：下面那条逐个旋钮的断言直接遍历 `TUNING_KEYS`。
    """
    assert set(TUNING_KEYS) >= {
        "hotness.gravity",
        "hotness.w_agg",
        "hotness.w_velocity",
        "hotness.w_accel",
        "hotness.novelty_weight",
        "burst.s",
        "burst.gamma",
        "weak_signal.agg_ceiling",
        "weak_signal.drift_penalty",
        "weak_signal.burst_coef",
        "theta_rel",
        "delta",
    }


@pytest.mark.parametrize("key", TUNING_KEYS)
def test_each_knob_actually_takes_effect(key: str) -> None:
    """逐个旋钮：配置里写一个不同的值，读出来就得是那个值。

    「配置读到了」与「配置生效了」是两件事——只测前者，改一个 key 名字
    就会静默回退到初值，而报告上仍写着「已标定」。
    """
    group, _, leaf = key.rpartition(".")
    payload: dict[str, object] = {group: {leaf: 9.5}} if group else {leaf: 9.5}

    profile = load_tuning(payload)

    holder = getattr(profile, group.replace(".", "_")) if group else profile
    assert getattr(holder, leaf if group else key) == 9.5


def test_an_unknown_key_is_refused_not_ignored() -> None:
    """配置里写错一个 key **必须报错**，NEVER 静默忽略。

    静默忽略的后果：owner 以为自己调了参，实际跑的还是初值，
    而对照表上两组数字一模一样——他会以为「这个参数没用」。
    """
    with pytest.raises(ValueError, match="typo_gravity"):
        load_tuning({"hotness": {"typo_gravity": 1.9}})


def test_an_unknown_group_is_refused_too() -> None:
    with pytest.raises(ValueError, match="hotnes"):
        load_tuning({"hotnes": {"gravity": 1.9}})


def test_a_partial_config_records_which_keys_came_from_it() -> None:
    """部分覆盖时，报告要说清**哪几个**来自配置、其余仍是初值。

    「已标定」是个整体印象，而真相往往是「θ_rel 标了，G 没标」。
    """
    profile = load_tuning({"theta_rel": 0.7})

    assert profile.overrides == ("theta_rel",)
    assert profile.hotness == HotnessConfig()      # 没写的仍是初值
    assert "theta_rel" in tuning_note(profile)


def test_the_profile_is_frozen() -> None:
    """profile 不可改——改一个已经标注过来源的配置，标注就成了假的。"""
    profile = load_tuning(None)

    with pytest.raises(Exception, match="(?i)frozen|cannot assign"):
        profile.calibrated = True  # type: ignore[misc]


def test_a_json_file_is_a_valid_source(tmp_path: Path) -> None:
    """配置可以来自文件（owner 交一份 json 就能跑）。"""
    path = tmp_path / "tuning.json"
    path.write_text(json.dumps({"burst": {"s": 3.0}}), encoding="utf-8")

    profile = load_tuning(path)

    assert profile.burst.s == 3.0
    assert profile.calibrated is True
    assert str(path) in profile.source


def test_a_missing_file_is_not_an_error_but_is_uncalibrated(tmp_path: Path) -> None:
    """文件不在 → 回落初值 + 未标定，**NEVER 抛**。

    抛的话，没有配置的机器上整条流水线跑不起来——而初值本来就是能跑的。
    """
    profile = load_tuning(tmp_path / "absent.json")

    assert profile.calibrated is False
    assert profile.hotness == HotnessConfig()


# ───────────────────────── 改配置能改出不同排序（acceptance①）


def test_changing_the_config_changes_the_ranking() -> None:
    """**这一条才是「生效」的证据**：同一批数据，两组参数排出的序不同。

    只断言「读到了值」证明不了什么——参数可能根本没被算式用到。
    """
    series = [
        _series("c-steady", agg=80.0, series=[80.0] * 7),      # 高但平
        _series("c-rising", agg=50.0, series=[5, 8, 12, 20, 32, 44, 50]),  # 低但陡
    ]
    today = TODAY

    flat = load_tuning({"hotness": {"w_velocity": 0.0, "w_accel": 0.0}})
    steep = load_tuning({"hotness": {"w_agg": 0.1, "w_velocity": 3.0, "w_accel": 2.0}})

    by_height = [s.cluster_id for s in rank_hotness(series, today, flat.hotness)]
    by_speed = [s.cluster_id for s in rank_hotness(series, today, steep.hotness)]

    assert by_height[0] == "c-steady"
    assert by_speed[0] == "c-rising"
    assert by_height != by_speed


# ───────────────────────── 跑批器：A/B 对照，恒 report_only


def test_the_runner_compares_two_profiles_on_the_same_data() -> None:
    """acceptance②：同一批数据两组参数，出对照表。"""
    from harness.tune_hotness import ab_compare

    series = [
        _series("c-steady", agg=80.0, series=[80.0] * 7),
        _series("c-rising", agg=50.0, series=[5, 8, 12, 20, 32, 44, 50]),
    ]
    report = ab_compare(
        series, TODAY,
        left=load_tuning({"hotness": {"w_velocity": 0.0, "w_accel": 0.0}}),
        right=load_tuning({"hotness": {"w_agg": 0.1, "w_velocity": 3.0, "w_accel": 2.0}}),
    )

    assert report["left"]["ranking"] == ["c-steady", "c-rising"]
    assert report["right"]["ranking"] == ["c-rising", "c-steady"]
    assert report["moved"] == ["c-rising", "c-steady"]


def test_the_runner_says_nothing_moved_when_nothing_moved() -> None:
    """阴性对照：两组参数一样时 `moved` 是空的——否则「有变化」这件事没有信息量。"""
    from harness.tune_hotness import ab_compare

    series = [_series("c-1", agg=80.0, series=[80.0] * 7)]
    same = load_tuning({"hotness": {"gravity": 1.6}})

    report = ab_compare(series, TODAY, left=same, right=same)

    assert report["moved"] == []


def test_the_runner_is_report_only_and_says_so() -> None:
    """acceptance②：**恒 report_only**——跑批器 NEVER 写回任何默认值。"""
    from harness.tune_hotness import ab_compare

    report = ab_compare(
        [_series("c-1", agg=80.0, series=[80.0] * 7)], TODAY,
        left=load_tuning(None), right=load_tuning({"hotness": {"gravity": 1.8}}),
    )

    assert report["report_only"] is True
    assert "未标定" in report["left"]["note"]


def test_the_runner_never_writes_anything_back() -> None:
    """源码面：跑批器里不许出现写回配置/改默认值的动作。

    调参是 owner 决策（S4 未决项）。一个能顺手写回的跑批器，
    迟早会有人「跑完顺便存一下」——那一刻未决项就被执行侧定了。
    """
    import inspect

    from harness import tune_hotness

    code = "\n".join(
        ln for ln in inspect.getsource(tune_hotness).split("\n")
        if not ln.strip().startswith("#")
    )
    for forbidden in ("write_text", "json.dump(", "os.environ[", "= HotnessConfig("):
        assert forbidden not in code, f"跑批器出现了写回动作：{forbidden}"


def test_the_defaults_in_the_three_modules_are_untouched() -> None:
    """本卡 NEVER 改任何默认值——三个模块的初值逐字不变（acceptance②）。

    数字写死在这里：改了它们的人会在这一条上红，然后被迫解释是不是 owner 定的。
    """
    h, b, w = HotnessConfig(), BurstConfig(), WeakSignalConfig()

    assert (h.gravity, h.w_agg, h.w_velocity, h.w_accel, h.novelty_weight) == (
        1.6, 1.0, 0.6, 0.3, 0.4)
    assert (b.s, b.gamma) == (2.0, 1.0)
    assert (w.agg_ceiling, w.drift_penalty, w.burst_coef) == (40.0, 1.0, 1.0)


def test_theta_rel_and_delta_defaults_are_untouched() -> None:
    """θ_rel 与 δ 的初值同样不动（S4 未决项，待金标集调参）。"""
    from flint.retrieval.relevance import THETA_REL

    assert THETA_REL == 0.6
    assert load_tuning(None).theta_rel == THETA_REL


# ───────────────────────── 与 GOLD-01 采集脚手架对接（acceptance④）


def test_the_runner_eats_gold_entries_from_the_collector(tmp_path: Path) -> None:
    """acceptance④：跑批器吃 `harness/gold_collect.py` 导出的 jsonl。"""
    from harness.gold_collect import GoldEntry, to_jsonl
    from harness.tune_hotness import series_from_gold

    entries = [
        GoldEntry(
            entry_id="e-1", job_id="j-1", kind="verdict",
            source_snapshot_id="s-1", source_ts="2026-07-20T00:00:00Z",
            payload={
                "cluster_id": "c-1",
                "first_seen": "2026-07-01",
                "agg_by_day": {"2026-07-14": 10.0, "2026-07-20": 70.0},
                "by_source_today": {"gtrends": 70.0},
            },
            label=None, note="",
        ),
    ]
    path = tmp_path / "gold.jsonl"
    path.write_text(to_jsonl(entries), encoding="utf-8")

    series = series_from_gold(path)

    assert [s.cluster_id for s in series] == ["c-1"]
    assert series[0].by_source_today == {"gtrends": 70.0}
    assert series[0].agg_by_day[date(2026, 7, 20)] == 70.0
    assert series[0].first_seen == date(2026, 7, 1)


def test_gold_entries_without_series_data_are_reported_not_skipped(tmp_path: Path) -> None:
    """吃不下的条目要**报出来**，NEVER 悄悄跳过。

    悄悄跳过的话，「拿 50 条金标跑的」可能实际只跑了 3 条，而对照表上看不出来。
    """
    from harness.tune_hotness import series_from_gold

    path = tmp_path / "gold.jsonl"
    path.write_text(
        json.dumps({"entry_id": "e-2", "kind": "judge", "payload": {"nothing": 1}}) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="e-2"):
        series_from_gold(path)


def test_the_profile_type_is_what_the_runner_expects() -> None:
    """通道与跑批器之间只有一种载体——两种载体迟早会有一种忘了带标注。"""
    assert isinstance(load_tuning(None), TuningProfile)
