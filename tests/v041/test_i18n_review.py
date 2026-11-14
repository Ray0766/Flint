"""K5-01：英文 UI 文案**机审**（DeepSeek 逐条审 + `needs_review` 标记）。

## K5 一直悬着的是什么

`WORKORDER-v04.md#7` 的 K5 行：「英文 UI 文案审校——需人工审校资源；
留空绕行方式 = en catalog 全量机翻占位 + `needs_review: true` 标记字段」。
人工资源没有，于是那 141 条 en 词条至今没人逐条看过。

本卡拿 DeepSeek 过一遍，**但机审 NEVER 冒充人工审校**：

- 审出来的问题与改写建议落**旁挂文件**（`web/messages/en.review.json`），
  `en.json` **一个字节不动**——键集一致性那几条既有断言继续绿；
- 每条都带 `needs_review: true` 与 `reviewed_by: "machine"`。
  **审过 ≠ 定稿**：人工确认之前它一直是待审状态。

## 为什么不直接把改写写回 en.json

写回去就等于「机器改的文案上线了」，而 `needs_review` 那个标记只在旁挂文件里——
下一个人打开 `en.json` 看到的是一份**看起来已经定稿**的目录。
改写以纯函数 `apply_suggestions()` 的形式提供，用不用是人的决定。

## 测试恒回放

`review_catalog` 收一个 provider 参数，测试注入替身，**一次真实调用都没有**。
真跑（含实际花费）在 `harness/i18n_review.py` 的 `__main__`，记在 trace 里。
"""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from harness.i18n_review import (
    ReviewFinding,
    ReviewReport,
    apply_suggestions,
    build_prompt,
    parse_review,
    review_catalog,
    sidecar_payload,
)

REPO = Path(__file__).resolve().parents[2]
EN = REPO / "web" / "messages" / "en.json"
ZH = REPO / "web" / "messages" / "zh.json"
SIDECAR = REPO / "web" / "messages" / "en.review.json"

SAMPLE = {
    "app.name": "Flint",
    "block.action.lock": "Lock",
    "settings.region.label": "Region",
}


class _Provider:
    """替身 provider：**测试恒回放**，一次真实调用都没有。"""

    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)
        self.purposes: list[str] = []
        self.prompts: list[str] = []
        self.ledger = _Ledger()

    def generate_with_purpose(self, prompt: str, *, purpose: str) -> object:
        self.prompts.append(prompt)
        self.purposes.append(purpose)
        reply = self._replies.pop(0)

        class _Completion:
            text = reply

        return _Completion()


class _Ledger:
    def reconcile(self) -> dict:
        return {"count": 1, "total_usd": Decimal("0.000123"),
                "input_tokens": 100, "output_tokens": 20,
                "cache_hit_tokens": 0, "pricing_versions": ["deepseek:0.14/0.28/none"],
                "mixed_pricing": False}


def _reply(findings: list[dict]) -> str:
    return json.dumps({"findings": findings}, ensure_ascii=False)


# ───────────────────────── 一、逐条审出问题与建议（acceptance①）


def test_the_prompt_names_the_three_things_to_check() -> None:
    """acceptance①：语法、术语一致性、是否像机翻——三样都要问到。

    问得含糊（「看看这些文案」）的话，模型会只挑最显眼的一类，
    而术语不一致恰恰是最不显眼的那类。
    """
    prompt = build_prompt(SAMPLE)
    # 判据只看**指令那一段**（`Entries:` 之前），不看整段提示词：
    # 回复格式那行里写着 `"ok|grammar|terminology|machine-translated"`，
    # 按全文判会被它喂饱——抽掉第 3 条指令，20 条照样全绿（变异考实测）。
    instructions = prompt.split("Entries:")[0]
    numbered = [ln for ln in instructions.splitlines() if ln[:2] in ("1.", "2.", "3.")]

    assert len(numbered) == 3, f"指令段里不是三条：{numbered}"
    for angle in ("grammar", "terminology", "machine-translated"):
        assert any(angle in ln for ln in numbered), f"指令段里没问到 {angle}"


def test_the_prompt_carries_every_entry_verbatim() -> None:
    """每条原文逐字进提示词——摘要或截断会让模型审的是另一份东西。"""
    prompt = build_prompt(SAMPLE)

    for key, value in SAMPLE.items():
        assert key in prompt and value in prompt


def test_findings_carry_a_kind_and_a_note() -> None:
    """一条问题要说清**是哪一类**与**为什么**，否则清单没法分诊。"""
    findings = parse_review(_reply([
        {"key": "app.name", "kind": "ok", "note": "brand name, fine"},
        {"key": "block.action.lock", "kind": "terminology",
         "note": "inconsistent with 'Unlock' elsewhere", "suggestion": "Lock block"},
    ]), expected=set(SAMPLE))

    assert {f.kind for f in findings} == {"ok", "terminology"}
    assert all(f.note for f in findings)


def test_a_finding_about_an_unknown_key_is_refused() -> None:
    """模型**编出来的 key** 直接报错，NEVER 静默丢掉。

    静默丢掉的话，「模型审了 141 条」与「模型审了 3 条外加编了 138 条」
    在结果上长得一模一样。
    """
    with pytest.raises(ValueError):
        parse_review(_reply([{"key": "not.a.real.key", "kind": "ok", "note": "x"}]),
                     expected=set(SAMPLE))


def test_a_missing_key_is_reported_not_ignored() -> None:
    """漏审的条目要报出来——漏审与「审过没问题」是两件事。"""
    with pytest.raises(ValueError) as err:
        parse_review(_reply([{"key": "app.name", "kind": "ok", "note": "fine"}]),
                     expected=set(SAMPLE), require_complete=True)

    assert "block.action.lock" in str(err.value)


def test_an_unparseable_reply_is_a_failure_not_an_empty_list() -> None:
    """结构化输出坏了就报错，NEVER 返回空清单当作「没问题」（S2-3）。"""
    for junk in ("", "not json", "{}", '{"findings": "nope"}'):
        with pytest.raises(ValueError):
            parse_review(junk, expected=set(SAMPLE))


def test_an_out_of_range_kind_is_refused() -> None:
    """`kind` 只认那四类。模型自己发明一类（`style` / `nitpick`）就报错——

    放行的话，清单上会出现没人知道该怎么处置的类别，
    而分诊表是按这四类写的（变异考实测：不校验 kind，20 条全绿）。
    """
    with pytest.raises(ValueError) as err:
        parse_review(_reply([{"key": "app.name", "kind": "style", "note": "x"}]),
                     expected=set(SAMPLE))

    assert "style" in str(err.value)


def test_a_finding_without_a_reason_is_refused() -> None:
    """`note` 空着就报错：**没有理由的结论没法分诊**。

    「这条有语法问题」而不说哪里有，读的人只能重新自己审一遍——
    那等于这次机审没发生（变异考实测：不校验 note，20 条全绿）。
    """
    for empty in ("", "   "):
        with pytest.raises(ValueError):
            parse_review(_reply([{"key": "app.name", "kind": "grammar", "note": empty}]),
                         expected=set(SAMPLE))


def test_a_suggestion_identical_to_the_original_is_dropped() -> None:
    """建议与原文一模一样 = 没有建议。留着它会让清单看起来有一堆待办。

    `expected` 这里传的是**带原文的 dict**：这件事只有知道原文才判得出来。
    """
    findings = parse_review(_reply([
        {"key": "app.name", "kind": "grammar", "note": "x", "suggestion": "Flint"},
    ]), expected=SAMPLE)

    assert findings[0].suggestion is None


# ───────────────────────── 二、审过 ≠ 定稿（acceptance②）


def test_every_reviewed_entry_stays_needs_review() -> None:
    """acceptance②：**NEVER 让机审冒充人工审校**。

    连判 `ok` 的也标——机器说没问题不等于人看过。
    """
    findings = [
        ReviewFinding(key="app.name", kind="ok", note="fine", suggestion=None),
        ReviewFinding(key="block.action.lock", kind="grammar", note="x",
                      suggestion="Lock block"),
    ]

    payload = sidecar_payload(findings, model="deepseek-v4-flash")

    assert all(item["needs_review"] is True for item in payload["entries"].values())
    assert all(item["reviewed_by"] == "machine" for item in payload["entries"].values())


def test_the_sidecar_records_which_model_reviewed_it() -> None:
    """标记要写清**谁审的**：换了模型重审时，旧结论与新结论要分得开。"""
    payload = sidecar_payload([], model="deepseek-v4-flash")

    assert payload["reviewed_by_model"] == "deepseek-v4-flash"
    assert payload["human_confirmed"] is False


def test_applying_a_suggestion_keeps_the_needs_review_flag() -> None:
    """采纳建议之后**仍是待审**——改写本身也是机器做的。"""
    findings = [ReviewFinding(key="block.action.lock", kind="grammar", note="x",
                              suggestion="Lock block")]

    rewritten, still_pending = apply_suggestions(dict(SAMPLE), findings)

    assert rewritten["block.action.lock"] == "Lock block"
    assert "block.action.lock" in still_pending


def test_applying_changes_nothing_without_a_suggestion() -> None:
    """阴性对照：没有建议的条目**一个字不改**。"""
    findings = [ReviewFinding(key="app.name", kind="ok", note="fine", suggestion=None)]

    rewritten, _ = apply_suggestions(dict(SAMPLE), findings)

    assert rewritten == SAMPLE


def test_the_harness_never_writes_the_shipped_catalog() -> None:
    """`en.json` **一个字节不动**：写回去等于机器改的文案上线了，

    而 `needs_review` 只在旁挂文件里——下一个人打开 `en.json`
    看到的是一份**看起来已经定稿**的目录。
    """
    import inspect

    from harness import i18n_review

    code = "\n".join(
        line for line in inspect.getsource(i18n_review).split("\n")
        if not line.strip().startswith("#")
    )

    assert "en.json" not in code or "write_text" not in code.split("en.json")[-1][:400]
    assert "EN_CATALOG.write_text" not in code


# ───────────────────────── 三、键集一致性不破（acceptance③）


def test_the_two_catalogs_still_have_the_same_keys() -> None:
    """acceptance③：zh 与 en 键完全对齐（既有断言的同一条口径）。"""
    zh = json.loads(ZH.read_text(encoding="utf-8"))
    en = json.loads(EN.read_text(encoding="utf-8"))

    assert set(zh) == set(en)


def test_the_sidecar_is_a_separate_file_not_a_catalog() -> None:
    """旁挂文件与目录**分开放**：混在一起的话，`t()` 会把标记当成一条文案。"""
    assert SIDECAR != EN
    if SIDECAR.exists():
        payload = json.loads(SIDECAR.read_text(encoding="utf-8"))
        en = json.loads(EN.read_text(encoding="utf-8"))
        assert set(payload["entries"]) <= set(en), "旁挂文件里有目录里没有的 key"


def test_the_sidecar_never_becomes_a_second_catalog() -> None:
    """旁挂文件里**不放译文本身**——放了就有了第二份目录，而两份里总有一份是旧的。"""
    payload = sidecar_payload(
        [ReviewFinding(key="app.name", kind="ok", note="fine", suggestion=None)],
        model="m")

    assert "text" not in payload["entries"]["app.name"]
    assert "value" not in payload["entries"]["app.name"]


# ───────────────────────── 四、走 JUDGE-01 的账本（acceptance④）


def test_the_review_goes_through_the_metered_provider() -> None:
    """acceptance④：**与 JUDGE-01 的用量账本打通**——用途标签也带上。"""
    provider = _Provider([_reply([
        {"key": k, "kind": "ok", "note": "fine"} for k in SAMPLE
    ])])

    report = review_catalog(provider, SAMPLE, batch_size=10)

    assert provider.purposes == ["i18n_review"]
    assert report.cost_usd == Decimal("0.000123")
    assert report.pricing_version == "deepseek:0.14/0.28/none"


def test_a_big_catalog_is_split_into_batches() -> None:
    """141 条一次塞进去会超上下文——分批，且**每批都记账**。"""
    entries = {f"k{i}": f"v{i}" for i in range(25)}
    provider = _Provider([
        _reply([{"key": f"k{i}", "kind": "ok", "note": "fine"} for i in range(10)]),
        _reply([{"key": f"k{i}", "kind": "ok", "note": "fine"} for i in range(10, 20)]),
        _reply([{"key": f"k{i}", "kind": "ok", "note": "fine"} for i in range(20, 25)]),
    ])

    report = review_catalog(provider, entries, batch_size=10)

    assert len(provider.purposes) == 3
    assert len(report.findings) == 25


def test_the_report_counts_what_needs_a_rewrite() -> None:
    """报告要能一眼看出**有多少条要改**，而不是只给一堆条目。"""
    report = ReviewReport(
        findings=[
            ReviewFinding(key="a", kind="ok", note="fine", suggestion=None),
            ReviewFinding(key="b", kind="grammar", note="x", suggestion="y"),
        ],
        cost_usd=Decimal(0), model="m", pricing_version="v", calls=1,
    )

    assert report.needs_rewrite == 1
    assert report.total == 2


def test_the_report_never_hides_a_zero_cost() -> None:
    """花费为 0 时也照实写 0——**没有花费**与**没记账**必须分得开。"""
    report = ReviewReport(findings=[], cost_usd=Decimal(0), model="m",
                          pricing_version="v", calls=0)

    assert report.cost_usd == Decimal(0)
    assert report.calls == 0


def test_the_module_makes_no_live_call_of_its_own() -> None:
    """审校逻辑零网络：请求由传进来的 provider 发（**它**才是唯一调用点）。"""
    import inspect

    from harness import i18n_review
    from tools.check_no_live_network import scan_source as net_scan

    assert net_scan(inspect.getsource(i18n_review), "harness/i18n_review.py") == []
