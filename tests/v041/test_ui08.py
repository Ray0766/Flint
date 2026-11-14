"""UI-08 · 账户屏（R1）与额度计费屏（R2）的结构判据。

交互判据在 vitest（18 条）。这里判源码结构与取证实况。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
ACCOUNT = REPO / "web" / "components" / "account-billing" / "AccountPanel.tsx"
BILLING = REPO / "web" / "components" / "account-billing" / "BillingPanel.tsx"
PAGES = (REPO / "web" / "app" / "account" / "page.tsx",
         REPO / "web" / "app" / "billing" / "page.tsx")
PROBE = REPO / ".ui-probe" / "fe_smoke.json"
ROUTES = ("/account", "/billing")


def _code_only(path: Path) -> str:
    text = re.sub(r"/\*[\s\S]*?\*/", "", path.read_text(encoding="utf-8"))
    return "\n".join(
        line for line in text.splitlines()
        if not line.lstrip().startswith(("//", "*"))
    )


# ───────────────────────── 一、金额与余量：前端一处运算都没有


def test_the_billing_panel_never_does_arithmetic() -> None:
    """蓝本铁律「零计算」在计费屏上的形态：

    - 金额恒是字符串（`Decimal` 走 JSON 浮点会把 0.1 + 0.2 变成 0.30000000000000004）；
    - 余量与合计都由后端算好。

    所以本组件里**没有任何算术运算符**，也不许把金额转成数字。
    """
    code = _code_only(BILLING)

    assert not re.search(r"[^=!<>+\-*/]\s[+\-*/]\s[^=]", code), "出现了算术运算"
    assert "Number(" not in code
    assert "parseFloat" not in code
    assert "toFixed" not in code
    assert ".reduce(" not in code


def test_the_remaining_is_taken_not_computed() -> None:
    code = _code_only(BILLING)

    assert "quota.remaining" in code
    assert "limit - " not in code
    assert "- billing.quota.used" not in code


def test_the_total_comes_from_the_backend() -> None:
    code = _code_only(BILLING)

    assert "reconciliation.total" in code


# ───────────────────────── 二、三种「没有」互不冒充


def test_not_provided_is_not_rendered_as_not_enabled() -> None:
    """「没查过」≠「计费未启用」≠「余额 0」。

    蓝本把 R2 记成 `billing_enabled: false`，那是**查过了**的状态；
    本屏此刻是**没查过**，两者在屏上说的话必须不同。
    """
    code = _code_only(BILLING)

    assert "billing === null" in code
    assert 'data-billing-state="not_provided"' in code or '"not_provided"' in code


def test_every_uncertain_state_has_its_own_marker() -> None:
    code = _code_only(ACCOUNT) + _code_only(BILLING)

    for marker in ("data-account-profile", "data-account-memberships",
                   "data-quota-state", "data-events-state"):
        assert marker in code, marker


def test_the_account_panel_keeps_the_three_profile_states_apart() -> None:
    code = _code_only(ACCOUNT)

    assert '"not_checked"' in code
    assert '"no_record"' in code
    assert '"known"' in code


# ───────────────────────── 三、NEVER 显示凭据


def test_no_credential_shaped_field_is_rendered() -> None:
    """BE-05 那侧连 import 都够不着凭据来源；前端这侧一个键都不渲染。"""
    code = _code_only(ACCOUNT) + _code_only(BILLING)

    assert not re.search(
        r"token|secret|password|credential|api_?key|authorization",
        code, re.IGNORECASE)


# ───────────────────────── 四、两屏本体


def test_neither_page_sends_a_request() -> None:
    for page in PAGES:
        code = _code_only(page)
        assert "fetch(" not in code, page.name
        assert "useEffect" not in code, page.name


def test_both_pages_take_the_backend_answer_and_fabricate_nothing() -> None:
    """`WIRE-03`：两屏改为真取数（`BE-05/06` 的端点已由 `WIRE-01` 挂上）。

    原判据是「传 `null`」——那是**未装配期间**的正确行为（`DEC-032`）。
    现在判的是同一件事的另一半：**屏上那个状态是后端给的，不是屏自己造的**。

    `not_enabled` 仍然 NEVER 出现在屏源码里：它是后端的结论，
    屏只负责把它渲染出来。屏里写死一个「未启用」，
    就等于在计费真的启用之后还说它没启用。
    """
    account_code = _code_only(PAGES[0])
    billing_code = _code_only(PAGES[1])

    assert "useScreenData" in account_code and "/account" in account_code
    assert "useScreenData" in billing_code and "/billing" in billing_code
    assert "account={null}" not in account_code
    assert "billing={null}" not in billing_code
    # 形状翻译交给适配层，屏里不做——屏里做就会各屏一份，迟早不一致。
    assert "toAccountView" in account_code and "toBillingView" in billing_code
    assert "not_enabled" not in billing_code, "NEVER 在屏上造一个「未启用」"


# ───────────────────────── 五、token 纪律与 i18n


def test_no_hardcoded_token_and_no_continuous_quantity() -> None:
    code = _code_only(ACCOUNT) + _code_only(BILLING) + "".join(
        _code_only(p) for p in PAGES)

    assert "%" not in code
    assert not re.search(r"#[0-9A-Fa-f]{3,8}\b", code)
    assert not re.search(r":\s*\d+px", code)


def test_every_string_shown_to_the_user_goes_through_i18n() -> None:
    for path in (ACCOUNT, BILLING, *PAGES):
        for literal in re.findall(r"[\"'`]([^\"'`]*)[\"'`]", _code_only(path)):
            assert not re.search(r"[一-龥]", literal), \
                f"{path.name} 里有裸中文：{literal!r}"


def test_the_keys_exist_in_both_dictionaries() -> None:
    zh = json.loads((REPO / "web" / "messages" / "zh.json").read_text(encoding="utf-8"))
    en = json.loads((REPO / "web" / "messages" / "en.json").read_text(encoding="utf-8"))
    source = "".join(p.read_text(encoding="utf-8") for p in (ACCOUNT, BILLING, *PAGES))
    used = set(re.findall(r't\("([^"]+)"', source))

    assert used
    for key in used:
        assert key in zh, key
        assert key in en, key


# ───────────────────────── 六、取证实况


def _rows(route: str) -> list[dict[str, object]]:
    if not PROBE.exists():
        pytest.skip("本机没跑过真栈冒烟：缺 .ui-probe/fe_smoke.json")
    report = json.loads(PROBE.read_text(encoding="utf-8"))
    if report.get("stack_down"):
        pytest.skip(f"上次实跑时栈没起：{report['stack_down']}")
    return [row for row in report["screens"] if row["route"] == route]


def test_both_new_screens_were_probed_in_both_themes() -> None:
    for route in ROUTES:
        assert {str(row["theme"]) for row in _rows(route)} == {"light", "dark"}, route


def test_both_new_screens_are_clean_on_the_real_stack() -> None:
    for route in ROUTES:
        for row in _rows(route):
            assert row["http_status"] == 200, row
            assert row["console_error_count"] == 0, row
            assert row["horizontal_overflow"] is False, row
            shot = REPO / ".ui-probe" / str(row["screenshot"])
            assert shot.exists() and shot.stat().st_size > 0, shot
