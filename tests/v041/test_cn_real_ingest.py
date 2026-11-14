"""CN-01：真实源抓取——**红线卡**，本卡只把一切准备到位，然后停下。

## 这份判据在判什么

`worker.md` §7 的事前必审四类之一是「真实网络或 API key 启用」，
`DEC-022` 授权的是 B 档抓取的**纪律形态**（抓完必录 `fixtures/`），
**欠的是首次实跑需 owner 在场**（`docs/blocked/E2E-REALSOURCE.md` 的原话）。

所以本卡的交付物不是「抓到了数据」，是**「准备到位 + 停得住」**：

1. 抓取脚本**一条命令可跑**；
2. 录制路径与命名**已定**（沿用 `E12` 布局，不新发明）；
3. 限速与 **429 / 5xx / ParseDrift** 三类错误处置**已接**；
4. 合规状态**照实记录**（`K2-01` 的 `RECORD_ONLY` 口径不变）；
5. **默认拒跑**——而且拒得吵：不带开关时一个请求都不发。

第 5 条是这份判据里最值钱的一条：前四条做到了而它没做到的话，
下一个连跑会话读到「脚本可一条命令跑」就会去跑它，
**而那正是 owner 保留给自己的那一次点头**。

## 「还没点头」与「点了但没抓到」NEVER 合并

两者在「库里没有真实热点」这个结果上长得一模一样。
所以脚本跑成之后会写一张回执（`docs/cn-01-real-ingest-receipt.json`），
下面「跑完之后」那一组判据**按回执在不在**决定是断言还是跳过——
跳过时把原因说成人话，NEVER 静静地绿。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "fixtures" / "_record_cn_real.py"
RECEIPT = REPO / "docs" / "cn-01-real-ingest-receipt.json"
TICKET = REPO / "docs" / "blocked" / "E2E-REALSOURCE.md"
SYNTHETIC = "热搜话题"


def _source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


# ───────────────────────── 一、准备到位：一条命令可跑


def test_the_recorder_exists_and_is_one_command() -> None:
    """`python fixtures/_record_cn_real.py`——**一条命令**，无需先配环境。

    住在 `fixtures/` 是沿用本仓既有惯例（`_generate_*.py` 都在那儿），
    也正好落在本卡 outputs 之内。
    """
    assert SCRIPT.exists(), "抓取脚本不在盘上"
    code = _source()

    assert 'if __name__ == "__main__":' in code, "不是一条命令能跑的脚本"
    assert "def main(" in code


def test_the_recording_path_and_naming_follow_the_existing_layout() -> None:
    """录制路径与命名**已定**且沿用 `E12`：`fixtures/{source_id}/{yyyy-mm-dd}.json`。

    自己发明一套的话，既有的回放路径（`build_replay_deps`）读不到它——
    抓回来的真数据会躺在盘上，而广场照旧显示合成词面。
    """
    code = _source()

    assert "fixture_path" in code, "没用既有的 E12 布局函数，自己拼了一套路径"
    assert "from flint.testing.replay import" in code


def test_the_two_cn_sources_are_the_ones_named_by_the_card() -> None:
    """本版只做中国区（`DEC-045`）：`weibo` + `gtrends` CN。"""
    code = _source()

    # `CN-06` 把录制器扩到四源。**两源那句话在当时是对的**——
    # 那时只有 weibo / gtrends 两个适配器碰过真实站点。
    assert 'CN_SOURCES = ("weibo", "gtrends", "ghtrend", "arxiv")' in code
    assert 'region="CN"' in code, "gtrends 没有钉在 CN"


# ───────────────────────── 二、限速与三类错误处置已接


def test_the_throttle_is_wired_and_reuses_the_existing_bucket() -> None:
    """限速走既有 `SourceThrottle`，**NEVER 另写一个**。"""
    code = _source()

    assert "from flint.sources.throttle import SourceThrottle" in code
    assert "throttle.configure(" in code
    assert "try_acquire" in code


def test_all_three_error_kinds_are_handled_and_named_apart() -> None:
    """**429 / 5xx / ParseDrift 各成一条结果**，NEVER 合并成「抓失败」。

    合并之后，一次限频与一次页面改版在日志里长得一样，
    而两者要做的事完全不同：前者等一会儿再来，后者要去改解析器。
    """
    code = _source()

    for name in ("RateLimitedError", "SourceFetchError", "ParseDrift"):
        assert f"except {name}" in code, f"没有单独接住 {name}"
    for outcome in ("rate_limited", "fetch_failed", "parse_drift"):
        assert f'"{outcome}"' in code, f"三类结果里少了 {outcome}"


def test_nothing_is_fabricated_when_a_source_cannot_be_reached() -> None:
    """抓不到的源**如实缺**——脚本里 NEVER 出现造词面的东西。"""
    code = _source()

    for forbidden in ("random", "faker", "lorem", "sample_keyword"):
        assert forbidden not in code.lower(), f"脚本里出现了造数据的痕迹：{forbidden}"


def test_every_successful_recording_writes_its_provenance() -> None:
    """**抓完必录**（`DEC-022` 授权的那条纪律）：fixture 与出处清单同时落盘。

    没有 manifest 的 fixture 等于没有出处，而「产物可复现」是 `S2-2` 第三条铁律。
    """
    code = _source()

    assert "write_manifest(" in code
    assert "make_provenance(" in code


def test_the_compliance_decision_is_recorded_not_re_judged() -> None:
    """合规状态**照实记录**（`K2-01` 的 `RECORD_ONLY`），且**不在这里重判一次**。

    重判就是第二个真相，而两份裁决迟早各说各的。
    """
    code = _source()

    assert "from flint.region.legal_policy import OWNER_DECISION" in code
    assert "OWNER_DECISION.scope" in code
    assert "admits(" not in code and "enforce_fetch_policy(" not in code, (
        "脚本自己又判了一次合规——裁决只有一处真相")


# ───────────────────────── 三、**停得住**（本组是本卡的核心）


def test_the_recorder_refuses_to_run_without_the_owner_present() -> None:
    """**默认拒跑**，退出码非 0，且一个请求都不发。

    这一条是本卡真正的交付物：前面几条做到了而这一条没做到的话，
    下一个连跑会话读到「一条命令可跑」就会去跑它——
    而那正是 owner 保留给自己的那一次点头。
    """
    done = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=120, check=False,
        env={**_utf8_env()},
    )

    assert done.returncode != 0, "不带开关竟然跑成了——红线没拦住"
    assert "owner" in done.stdout.lower(), f"拒得不够清楚：{done.stdout[:400]}"
    assert "不发任何请求" in done.stdout


def test_the_switch_is_an_explicit_flag_not_an_environment_variable() -> None:
    """开关 MUST 是**命令行上看得见的那一个**。

    环境变量会被 `.env`、被 CI 配置、被上一条命令留在 shell 里的值悄悄打开，
    而这一次点头必须是当场、显式、看得见的。
    """
    code = _source()

    assert '"--owner-is-here"' in code
    assert "getenv" not in code and "environ" not in code, (
        "开关被做成了环境变量——那样它会被悄悄打开")


def test_the_dry_run_prints_what_it_would_do() -> None:
    """拒跑时**说清将要做什么**：抓哪两源、录到哪、合规裁决是什么。

    只说「拒绝」的话，owner 要点头之前得自己去读脚本。
    """
    done = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=120, check=False, env={**_utf8_env()},
    )
    out = done.stdout

    assert "weibo" in out and "gtrends" in out
    assert "fixtures" in out, "没说清录到哪儿"
    assert "non_commercial" in out, "没把合规裁决打出来"


def _utf8_env() -> dict[str, str]:
    import os

    return {**os.environ, "PYTHONIOENCODING": "utf-8"}


def test_the_ticket_was_closed_by_the_run_that_actually_happened() -> None:
    """`docs/blocked/E2E-REALSOURCE.md` 由 `CN-06` 关掉。

    这条判据原来钉的是「保持 open，直到 owner 点过」，理由是
    「单据先关掉的话，『等一次点头』这件事就从盘上消失了，而脚本仍然拒跑」。
    **那个理由在当时是对的**——那时唯一的授权路是 `--owner-is-here`。

    `DEC-052` 之后多了第二条路（预授权），`CN-06` 走它跑成了那一次端到端录制。
    所以断言跟着翻面，**而翻的是「谁点的头」，不是「要不要点头」**：
    脚本默认照旧拒跑，两个旗标各说各的语义（下面两条判据钉着）。

    判的是**留痕**而不是 `open` 那个字（`GAUGE-16` 立的判法）：
    单还在、状态行说得出是谁在哪一天关的、关闭那一节点名它。
    """
    from tests.v041._sheet_trace import assert_sheet_keeps_its_trace

    state, _day, card = assert_sheet_keeps_its_trace(TICKET)

    assert state == "closed"
    assert card == "CN-06", card
    # 「要一次点头」这件事**照旧留在单子上**——关掉的是那一次运行，不是那条纪律。
    assert "在场" in TICKET.read_text(encoding="utf-8")


# ───────────────────────── 四、跑完之后（owner 点过才断言）


def _receipt() -> dict[str, object]:
    if not RECEIPT.exists():
        pytest.skip(
            "CN-01 还在等 owner 在场点一次——脚本准备到位、默认拒跑，"
            "跑过之后会写 docs/cn-01-real-ingest-receipt.json，"
            "那时下面几条自动开始判。**这不是失败，是红线内的刻意不做。**")
    return json.loads(RECEIPT.read_text(encoding="utf-8"))


def test_the_receipt_records_which_sources_actually_came_back() -> None:
    """回执逐源记 outcome——**「跑过了」与「跑成了」是两件事**。"""
    receipt = _receipt()
    results = receipt["results"]

    assert isinstance(results, list) and results
    for row in results:
        assert row["outcome"] in (
            "ok", "rate_limited", "fetch_failed", "parse_drift"), row


def test_the_plaza_has_no_synthetic_labels_after_a_real_run() -> None:
    """跑完之后广场上 NEVER 再出现 `热搜话题NN` 这类合成词。

    **全库扫描该模式，命中即红**（卡面原话）。
    扫的是当天那两份 fixture：广场读的就是它们经 `daily_ingest` 灌进去的东西。
    """
    receipt = _receipt()
    day = receipt["day"]
    ok = [r["source"] for r in receipt["results"] if r["outcome"] == "ok"]
    if not ok:
        pytest.skip("那一次跑一个源都没抓到（回执里逐源记着原因）——如实缺，不编词面")

    for source in ok:
        fixture = REPO / "fixtures" / str(source) / f"{day}.json"
        assert SYNTHETIC not in fixture.read_text(encoding="utf-8"), (
            f"{fixture} 里还有合成词面——那一次录制没有覆盖掉旧夹具")
