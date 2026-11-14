"""TYPE-06：`frontend_untyped_response` 清零——**这一类是真的一个都没建**。

与 `TYPE-05` 那七条不同：那七条被尺子**认错了接口**（双字段巧合），
这一类是真的没有类型。`GAUGE-14` 修掉对账器两个盲区之前，这些调用点扫不到，
**其响应类型自然无从比对**——它们不是新引入的缺口，是第一次被看见。

## 清单以**实跑**为准，NEVER 照记忆写

卡面写「八条」。`TYPE-05` 收尾时 `/settings/locale` 与两条 deref
（`/citations/{}` `/price-entries/{}`）已经顺带建了，所以本卡实际做**五条**：
`/account` · `/billing` · `/design/sessions/{}/replay` · `/design/templates` ·
`/interventions/lock`。

这个差额如实记在这里——照卡面那个八去找，会有三条怎么也找不到。

## 这一族的形状有一条共同纪律：**四种「没有」互不合并**

`not_checked`（没查过）· `no_record`（查过了没有）· `not_enabled`（能力在但没配）·
`not_provided`（这一族还没有后端）。前端把它们折成一个 `null`，
屏上就只剩「没有」两个字，而这四件事要用户做的完全不同（`DEC-032`）。

## 单键响应那条：尺子改了一处，不是放宽门槛

`/interventions/lock` 的响应键只有 `locked` 一个。
`_best_interface` 的门槛是「至少两个字段重合」——**它在单键响应上结构性地迈不过去**：
无论前端怎么写都凑不出两个重合字段，于是那条端点**恒被报成「根本没建类型」，
而建了也不算**。

改法要求**接口字段集与响应字段集完全相等**——那不是巧合，是精确匹配。
下面 `test_a_single_key_response_still_needs_an_exact_match` 是它的阴性对照。
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

LIB = REPO / "web" / "lib"
ACCOUNT_TYPES = LIB / "accountTypes.ts"
TICKET = REPO / "docs" / "blocked" / "PARITY-WIDER-SCAN-REVEALS-FIFTEEN-TYPE-GAPS.md"

# 本卡实际经手的五条（卡面写八条，差额见模块 docstring）。
NAMED = (
    "/account", "/billing", "/design/sessions/{}/replay",
    "/design/templates", "/interventions/lock",
)


def _report() -> dict[str, object]:
    done = subprocess.run(
        [sys.executable, str(REPO / "tools" / "check_fe_be_parity.py"), "--json"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=REPO, timeout=300, check=False)
    assert done.stdout.strip(), done.stderr[-2000:]
    return json.loads(done.stdout[done.stdout.index("{"):])


def _interfaces() -> dict[str, str]:
    return dict(re.findall(
        r"export\s+interface\s+(\w+)(?:<[^>]*>)?\s*\{(.*?)\n\}",
        ACCOUNT_TYPES.read_text(encoding="utf-8"), re.DOTALL))


# ───────────────────────── 一、两类计数都归零


def test_no_endpoint_is_reported_as_untyped() -> None:
    """**本卡的出口判据**：`frontend_untyped_response` 计数为 0。"""
    found = [f for f in _report()["findings"]  # type: ignore[index]
             if f["kind"] == "frontend_untyped_response"]  # type: ignore[index]

    assert found == [], "还有端点没有类型：" + ", ".join(
        f"{f['subject']}（缺 {f.get('expected')}）" for f in found)


def test_the_other_type_class_is_still_zero_too() -> None:
    """`TYPE-05` 清掉的那一类**没有因为本卡而复活**。

    本卡新增了一批接口，而 `_best_interface` 是「挑最像的那一个」——
    新接口可能把某条端点从一个正确的匹配上抢走。这条判据挡的正是那个。
    """
    found = [f for f in _report()["findings"]  # type: ignore[index]
             if f["kind"] == "field_mismatch"]  # type: ignore[index]

    assert found == [], "本卡把 TYPE-05 清掉的那一类又碰红了：" + ", ".join(
        str(f["subject"]) for f in found)


def test_each_of_the_five_is_clean_by_name() -> None:
    """五条**逐条**点名——只判总数的话，「它们从此扫不到了」也能让计数归零。"""
    reported = {str(f["subject"]) for f in _report()["findings"]  # type: ignore[index]
                if f["kind"] in ("frontend_untyped_response", "field_mismatch")}  # type: ignore[index]

    still = [path for path in NAMED if path in reported]
    assert still == [], f"这几条还在被报：{still}"


def test_the_checker_did_not_go_blind() -> None:
    """**反向守卫**：尺子没有变成「什么都不报」。"""
    findings = _report()["findings"]

    assert findings, "对账器一条都不报了"
    assert any(f["kind"] == "backend_unused_by_frontend" for f in findings)  # type: ignore[index]


# ───────────────────────── 二、四种「没有」互不合并


def test_the_four_kinds_of_absence_are_each_their_own_branch() -> None:
    """`not_checked` / `no_record` / `not_enabled` / `not_provided` **各是各的**。

    折成一个 `null`，屏上就只剩「没有」两个字，
    而这四件事要用户做的完全不同（`DEC-032`）。
    """
    text = ACCOUNT_TYPES.read_text(encoding="utf-8")

    # 判**这四个词出现在文件里**，而不是判它们都是字面量类型：
    # 具名分支（`DesignTemplatesNotProvided`）的 `status` 写成 `string`——
    # 那是为了让对账器看见这个字段（它只扫 `export interface`），
    # 而那一态**是靠接口名与注释区分的**，不是靠字面量类型。
    # 判「必须是字面量」会把这个正确的取舍判成错。
    for state in ("not_checked", "no_record", "not_enabled", "not_provided"):
        assert state in text, f"{state} 这一态没建"


def test_the_union_branches_are_named_interfaces_where_the_ruler_can_see_them() -> None:
    """联合的分支**具名**。

    写成匿名字面量时对账器看不见它们的字段（它只扫 `export interface`）——
    `reconciliation` 这种只出现在一个分支里的字段就会被判成「前端没声明」。
    本卡实测撞过这一条。
    """
    names = _interfaces()

    for wanted in ("BillingEventsChecked", "DesignTemplatesList",
                   "DesignTemplatesNotProvided"):
        assert wanted in names, f"{wanted} 不是一个具名接口"
    assert "reconciliation" in names["BillingEventsChecked"]


def test_money_is_a_string_not_a_number() -> None:
    """**钱恒是字符串**——浮点会在对账时差出分。

    后端 `event_json` 逐字写着 `str(event.amount)`；前端声明成 `number`
    会让 `JSON.parse` 之后的值静静变成浮点，而对账表上那一栏看起来完全正常。
    """
    names = _interfaces()

    assert re.search(r"amount:\s*string", names["BillingEventRow"]), "amount 不是字符串"
    assert re.search(r"total:\s*string", names["BillingReconciliation"])


def test_the_quota_numbers_are_the_backends_not_recomputed() -> None:
    """`remaining` / `exhausted` 是**后端给的**，类型里都在。

    少声明一个，前端就会拿 `limit - used` 自己算一遍——
    而超额判定来自后端的同一次判定，两处迟早给出不同答案。
    """
    text = ACCOUNT_TYPES.read_text(encoding="utf-8")

    for field in ("remaining", "exhausted", "shortfall"):
        assert f"{field}:" in text, f"额度里少了 {field}"


# ───────────────────────── 三、NEVER 编一个不存在的「响应」


def test_the_lock_type_is_the_edit_after_image_not_a_response() -> None:
    """`/interventions/lock` 成功时回 **204 无体**。

    `locked` 那个键出现在它写进 `EditEvent.after` 的记录里
    （对账器把处理函数里所有字面量 dict 的键都算作这条路由的键）。
    **编一个 `{ locked: true }` 的「响应」能让尺子闭嘴，而那种响应根本不存在**——
    照它去读 `res.locked` 拿到的永远是 `undefined`。
    """
    text = ACCOUNT_TYPES.read_text(encoding="utf-8")
    names = _interfaces()

    assert "LockEditAfter" in names, "那个后像类型不在"
    assert "LockResponse" not in names, "又编了一个不存在的响应类型"
    assert "204" in text, "没写清这条端点其实不回体"


# ───────────────────────── 四、尺子那一处改动：精确匹配，不是放宽门槛


def test_a_single_key_response_is_matched_by_an_exact_interface() -> None:
    """单键响应 + 字段集完全相等的接口 = 匹配。

    改前那道「至少两个字段重合」的门在单键响应上**结构性地迈不过去**：
    无论前端怎么写都凑不出两个重合字段。
    """
    from tools.check_fe_be_parity import _best_interface

    best, covered = _best_interface({"locked"}, {"x.ts#LockEditAfter": {"locked"}})

    assert best == "x.ts#LockEditAfter"
    assert covered == {"locked"}


def test_a_single_key_response_still_needs_an_exact_match() -> None:
    """**阴性对照**：那一处改的是「精确匹配」，NEVER 是「放宽门槛」。

    一个**恰好也有这个字段**、但还带着别的字段的接口，仍然不算——
    它不是这条响应的类型，它只是碰巧提到了同一个词。
    """
    from tools.check_fe_be_parity import _best_interface

    bigger, _ = _best_interface({"locked"}, {"x.ts#Something": {"locked", "extra"}})
    unrelated, _ = _best_interface({"locked"}, {"x.ts#Other": {"a", "b"}})

    assert bigger is None, "一个更大的接口被当成了单键响应的类型"
    assert unrelated is None


def test_the_two_key_threshold_is_untouched_for_bigger_responses() -> None:
    """**多键响应那道门一字未改**：一个同名字段仍然不算证据。"""
    from tools.check_fe_be_parity import _best_interface

    best, _ = _best_interface(
        {"fact_id", "statement", "value"}, {"x.ts#Coincidence": {"value", "other"}})

    assert best is None, "一个字段的巧合又开始算数了"


# ───────────────────────── 五、单据关掉（两类均清零）


def test_the_ticket_is_closed_now_that_both_classes_are_zero() -> None:
    text = TICKET.read_text(encoding="utf-8")
    head = "\n".join(text.splitlines()[:8])

    assert "**状态** closed" in head, f"单据还开着：{head!r}"
    assert "TYPE-05" in text and "TYPE-06" in text, "关单没写是被哪两张卡清的"
    assert "15" in text, "单子里那个数被抹掉了——它是这次发现的规模"


def test_the_ticket_records_that_the_card_said_eight_but_five_were_left() -> None:
    """卡面写八条、实际五条——**差额如实记在单子里**。

    不记的话，下一个人照卡面那个八去找，会有三条怎么也找不到。
    """
    text = TICKET.read_text(encoding="utf-8")

    assert "settings/locale" in text, "没记下它是被哪张卡顺带建的"
    assert "五条" in text or "5 条" in text
