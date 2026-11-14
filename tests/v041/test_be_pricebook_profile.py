"""BE-11 · PriceBook 与 Profile 读端点（暴露 `flint/pricebook` + `flint/profile`）。

支撑报告里 **PriceCell** 与 **ProfileRef** 两个通道的解引用。

三条判据线：

1. **三通道 NEVER 混用（S2-2）**——价格那条路上不出现 profile 字段，
   涉我那条路上不出现价格；两条路都不碰 Fact 通道（那是 FB-04 的事）。
2. **过期价照实标、NEVER 静默用旧价**——时效状态与价格**一起返回**，
   判定转调既有 `check_stale`（30.44 天/月的日粒度口径写在那里）。
3. **视角 NEVER 由调用方说了算**——`viewer_role` 是**判出来的**，不是请求里带的。
   带得进来就等于自称 owner，D12 的敏感度口径当场作废。
"""
from __future__ import annotations

import ast
import re
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from flint.api.pricebook import PriceProfileApiDeps, create_pricebook_app
from flint.domain.models import PriceEntry, Principal, UserProfile

MODULE = Path("flint/api/pricebook.py")

ME = "u-me"
OTHER = "u-other"
TODAY = date(2026, 8, 5)


def _entry(entry_id: str = "pe-1", *, updated: datetime | None = None,
           source: str = "https://example.gov/price", months: int = 12) -> PriceEntry:
    return PriceEntry(
        entry_id=entry_id, item="服务器托管", unit="台/月",
        price_low=800.0, price_high=1200.0, currency="CNY", region="CN",
        year=2026, source=source,
        updated_at=updated or datetime(2026, 6, 1, tzinfo=UTC),
        stale_after_months=months,
    )


def _profile(owner: str = ME, **overrides: Any) -> UserProfile:
    fields: dict[str, Any] = {
        "profile_id": "pf-1",
        "owner": Principal(kind="user", id=owner),
        "identity": {"name": "某研究者", "org": "某机构"},
        "research": {"publications": ["论文一", "论文二"]},
        "team": [{"size": "3"}],
        "assets": {"lab": "有"},
        "constraints": {"budget_range": "50-80 万", "timeline": "12 个月"},
        "track_record": [{"grants": "两项"}],
        "locale": "zh-CN",
        "sensitivity_overrides": {},
        "updated_at": datetime(2026, 5, 1, tzinfo=UTC),
    }
    fields.update(overrides)
    return UserProfile(**fields)


def _app(
    *, entries: list[PriceEntry] | None = None,
    profile: UserProfile | None = None,
    viewer_role: str | None = None,
) -> TestClient:
    rows = list(entries or [])
    kept = profile

    async def load_entries() -> list[PriceEntry]:
        return list(rows)

    async def load_profile(profile_id: str) -> UserProfile | None:
        if kept is None or profile_id != kept.profile_id:
            return None
        return kept

    def role_for(caller: Principal, loaded: UserProfile) -> str | None:
        """本卡的注入点：调用方相对这份 profile 是什么视角。"""
        if loaded.owner.kind == caller.kind and loaded.owner.id == caller.id:
            return "owner"
        return viewer_role       # None = 看不到（没有 memberships 表，无从确认同事）

    deps = PriceProfileApiDeps(
        load_entries=load_entries, load_profile=load_profile,
        viewer_role_for=role_for, today=lambda: TODAY,
    )
    return TestClient(create_pricebook_app(deps))


def _get(client: TestClient, path: str, user: str = ME) -> Any:
    return client.get(path, headers={"X-User-Id": user})


def _identifiers() -> set[str]:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {
        n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}


# ───────────────────────── 一、PriceCell 通道（acceptance①③）


def test_an_empty_pricebook_is_an_empty_list_not_404() -> None:
    client = _app()

    response = _get(client, "/pricebook")

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_an_entry_carries_the_frozen_fields_and_its_freshness() -> None:
    client = _app(entries=[_entry()])

    body = _get(client, "/pricebook/pe-1").json()

    assert body["entry_id"] == "pe-1"
    assert body["price_low"] == 800.0
    assert body["price_high"] == 1200.0
    assert body["currency"] == "CNY"
    assert body["source"] == "https://example.gov/price"
    assert body["freshness"] == {"stale": False, "yellow_flag": False, "year": 2026}


def test_a_stale_entry_is_returned_with_its_flag_never_silently() -> None:
    """过期仍可用，但**双重标注缺一不可**：黄标位 + 年份注记。

    静默用旧价 = 报告里那个数看起来和新价一模一样，而它是两年前的。
    """
    old = _entry(updated=datetime(2023, 1, 1, tzinfo=UTC))
    client = _app(entries=[old])

    body = _get(client, "/pricebook/pe-1").json()

    assert body["price_low"] == 800.0, "过期不等于不给——给，但要标"
    assert body["freshness"]["stale"] is True
    assert body["freshness"]["yellow_flag"] is True
    assert body["freshness"]["year"] == 2023


def test_the_staleness_is_delegated_not_recomputed() -> None:
    """30.44 天/月那个口径只有一份实现：模块里 NEVER 出现自己算的天数。"""
    assert "check_stale" in _identifiers()

    # 天数口径与月份折算只有一份实现：模块里既没有那个**常数**，
    # 也没有任何时间差运算（`timedelta` / 日期相减）。
    # 判 AST 而不是全文——本模块的 docstring 里就写着「30.44 天/月的口径在那里」，
    # 判全文会被自己的注释喂饱（本轮第八次撞上这个形状）。
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    numbers = {n.value for n in ast.walk(tree)
               if isinstance(n, ast.Constant) and isinstance(n.value, int | float)}

    assert 30.44 not in numbers
    assert "timedelta" not in _identifiers()


def test_the_data_notes_come_from_the_existing_helper() -> None:
    """质量卡那句「单价数据为 {year} 年」也转调既有实现。"""
    old = _entry(updated=datetime(2023, 1, 1, tzinfo=UTC))
    client = _app(entries=[old, _entry("pe-2")])

    body = _get(client, "/pricebook").json()

    assert body["notes"] == ["单价数据为 2023 年"]
    assert "price_data_notes" in _identifiers()


def test_an_unknown_entry_is_404() -> None:
    client = _app(entries=[_entry()])

    response = _get(client, "/pricebook/pe-nope")

    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_an_entry_without_a_source_is_marked_uncitable() -> None:
    """无出处的条目**不可被预算表引用**（`make_price_cell` 的原话）。

    这里不拒绝返回它——查得到是一回事，能不能引是另一回事；
    但**必须说出来**，否则调用方会拿它去填单元格。
    """
    client = _app(entries=[_entry(source="")])

    body = _get(client, "/pricebook/pe-1").json()

    assert body["citable"] is False


def test_a_sourced_entry_is_citable() -> None:
    client = _app(entries=[_entry()])

    assert _get(client, "/pricebook/pe-1").json()["citable"] is True


# ───────────────────────── 二、ProfileRef 通道（acceptance①③）


def test_resolving_my_own_profile_field_returns_a_ref_and_the_value() -> None:
    client = _app(profile=_profile())

    body = _get(client, "/profile/pf-1/fields/identity.name").json()

    assert body["ref"] == {"kind": "profile", "field_path": "identity.name"}
    assert body["value"] == "某研究者"


def test_an_indexed_path_resolves() -> None:
    """两级路径 + `[index]` 口径（`research.publications[1]`）。"""
    client = _app(profile=_profile())

    body = _get(client, "/profile/pf-1/fields/research.publications[1]").json()

    assert body["value"] == "论文二"


def test_a_missing_field_is_a_data_gap_not_a_404() -> None:
    """查询合法但没内容 → 缺口，不是 404。缺的是资料，说清楚才能补。"""
    client = _app(profile=_profile())

    response = _get(client, "/profile/pf-1/fields/identity.nope")

    assert response.status_code == 200
    assert response.json()["gap"]["cause"] == "missing_data"
    assert "value" not in response.json()


def test_an_owner_only_field_is_a_permission_gap_never_disguised_as_missing_data() -> None:
    """审8：`missing_permission` **绝不伪装成缺资料**。

    伪装成缺资料的话，团队成员会去「补录」一份 owner 不想给他看的东西。
    """
    client = _app(profile=_profile(owner=OTHER), viewer_role="team")

    body = _get(client, "/profile/pf-1/fields/constraints.budget_range").json()

    assert body["gap"]["cause"] == "missing_permission"
    assert body["gap"]["required_scope"] == "constraints.budget_range"
    assert body["gap"]["suggested_sources"] == []
    assert "50-80" not in str(body)


def test_a_team_viewer_still_sees_the_non_sensitive_fields() -> None:
    client = _app(profile=_profile(owner=OTHER), viewer_role="team")

    body = _get(client, "/profile/pf-1/fields/constraints.timeline").json()

    assert body["value"] == "12 个月"


def test_the_whole_profile_view_drops_owner_only_fields_for_a_team_viewer() -> None:
    """过滤在**读取面**执行——无权字段不出库（M3-014 的硬条款）。"""
    client = _app(profile=_profile(owner=OTHER), viewer_role="team")

    body = _get(client, "/profile/pf-1").json()

    assert "budget_range" not in str(body)
    assert body["constraints"] == {"timeline": "12 个月"}


def test_the_owner_sees_their_own_sensitive_fields() -> None:
    client = _app(profile=_profile())

    body = _get(client, "/profile/pf-1").json()

    assert body["constraints"]["budget_range"] == "50-80 万"


def test_a_stranger_gets_404_not_a_filtered_profile() -> None:
    """没有 memberships 表就无从确认「同事」——确认不了就是看不到。

    给一份过滤后的 profile 等于承认「这个 profile 存在」。
    """
    client = _app(profile=_profile(owner=OTHER), viewer_role=None)

    response = _get(client, "/profile/pf-1")

    assert response.status_code == 404
    assert "某研究者" not in response.text


def test_an_unknown_profile_is_404_with_the_same_code() -> None:
    client = _app(profile=_profile(owner=OTHER), viewer_role=None)

    unknown = _get(client, "/profile/pf-nope")
    theirs = _get(client, "/profile/pf-1")

    assert unknown.status_code == theirs.status_code == 404
    assert unknown.json()["code"] == theirs.json()["code"] == "NOT_FOUND"


def test_the_viewer_role_is_never_taken_from_the_request() -> None:
    """带得进来就等于自称 owner，D12 的敏感度口径当场作废。"""
    client = _app(profile=_profile(owner=OTHER), viewer_role="team")

    body = client.get(
        "/profile/pf-1?viewer_role=owner",
        headers={"X-User-Id": ME, "X-Viewer-Role": "owner"}).json()

    assert "budget_range" not in str(body)


def test_no_handler_declares_a_role_parameter() -> None:
    """判在签名上：处理函数的参数里除路径外每一个都得是 `Header(...)`，
    且没有任何叫 role 的东西——声明出来就迟早有人接上去。"""
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.AsyncFunctionDef):
            continue
        if not any(isinstance(d, ast.Call) for d in node.decorator_list):
            continue
        names = [a.arg for a in node.args.args]
        assert not [n for n in names if "role" in n.lower()], node.name
        for name, default in zip(names[-len(node.args.defaults):],
                                 node.args.defaults, strict=True) \
                if node.args.defaults else []:
            assert isinstance(default, ast.Call), f"{node.name}.{name} 是查询串参数"


# ───────────────────────── 三、三通道 NEVER 混用（acceptance②）


def test_the_price_route_never_returns_a_profile_field() -> None:
    client = _app(entries=[_entry()], profile=_profile())

    body = _get(client, "/pricebook/pe-1").json()

    assert "field_path" not in str(body)
    assert "某研究者" not in str(body)


def test_the_profile_route_never_returns_a_price() -> None:
    client = _app(entries=[_entry()], profile=_profile())

    body = _get(client, "/profile/pf-1/fields/identity.name").json()

    assert "price" not in str(body).replace('"kind":"profile"', "")
    assert "entry_id" not in str(body)


def test_the_module_never_touches_the_fact_channel() -> None:
    """Fact 通道走 FB-04（`flint/api/deref.py`），本模块**够不着它**。

    三通道混用的第一步恒是「顺手在这里也解一下 fact」。
    """
    identifiers = _identifiers()

    assert "deref" not in identifiers
    assert not {"fact_id", "claim_id", "citation_id"} & identifiers


def test_the_price_cell_constructor_is_the_existing_one() -> None:
    """能不能引由既有 `make_price_cell` 的口径说了算，本模块 NEVER 另判一次。"""
    assert "make_price_cell" in _identifiers()


# ───────────────────────── 四、只读与结构判据（acceptance④⑥）


def test_identity_is_required_everywhere() -> None:
    client = _app(entries=[_entry()], profile=_profile())

    assert client.get("/pricebook").status_code == 422
    assert client.get("/pricebook/pe-1").status_code == 422
    assert client.get("/profile/pf-1").status_code == 422


def test_the_module_writes_no_sql_of_its_own() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    docstrings = {ast.get_docstring(n) for n in ast.walk(tree)
                  if isinstance(n, ast.Module | ast.ClassDef | ast.FunctionDef
                                | ast.AsyncFunctionDef)}
    literals = " ".join(
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        and node.value not in docstrings
    )

    for pattern in (r"INSERT\s+INTO", r"DELETE\s+FROM", r"UPDATE\s+\w+\s+SET",
                    r"DROP\s+(TABLE|COLUMN)", r"ALTER\s+TABLE"):
        assert not re.search(pattern, literals, re.IGNORECASE), f"模块里有 {pattern}"

    assert not {"asyncpg", "sqlalchemy"} & _identifiers()


def test_no_field_is_synthesised_on_the_price_route() -> None:
    client = _app(entries=[_entry()])

    body = _get(client, "/pricebook/pe-1").json()

    assert set(body) == {
        "entry_id", "item", "unit", "price_low", "price_high", "currency",
        "region", "year", "source", "updated_at", "stale_after_months",
        "freshness", "citable"}


def test_no_field_is_synthesised_on_the_profile_route() -> None:
    """变异⑰ 逼出来的：价格那条路有形状判据，涉我这条路当时**一条都没有**——
    于是往响应里加一个 `owner_id` 全绿，而那正是「把别人身份带出去」。"""
    client = _app(profile=_profile())

    body = _get(client, "/profile/pf-1").json()

    assert set(body) == {"profile_id", "identity", "research", "team", "assets",
                         "constraints", "track_record", "locale", "updated_at"}


def test_no_channel_key_leaks_into_the_profile_response() -> None:
    """三通道判据也要判**响应键**，不能只判模块标识符。

    变异⑲ 往响应里塞了个 `"fact_id"` ——它是个字符串键，不是标识符，
    于是从「模块够不着 Fact 通道」那条判据下面走了过去。
    """
    client = _app(profile=_profile())

    def keys(node: Any) -> list[str]:
        if isinstance(node, dict):
            return [k for key, v in node.items() for k in [key, *keys(v)]]
        if isinstance(node, list):
            return [k for v in node for k in keys(v)]
        return []

    for path in ("/profile/pf-1", "/profile/pf-1/fields/identity.name"):
        found = set(keys(_get(client, path).json()))
        assert not [k for k in found
                    if re.search(r"fact|citation|claim|price|entry_id", k)], path


def test_the_two_kinds_of_404_share_one_code_on_the_field_route_too() -> None:
    """字段那条路上的两种 404 也要同一个码——变异⑳ 就是从这条缝里活下来的。"""
    client = _app(profile=_profile(owner=OTHER), viewer_role=None)

    unknown = _get(client, "/profile/pf-nope/fields/identity.name")
    theirs = _get(client, "/profile/pf-1/fields/identity.name")

    assert unknown.status_code == theirs.status_code == 404
    assert unknown.json()["code"] == theirs.json()["code"] == "NOT_FOUND"


def test_no_total_is_computed_without_a_quantity() -> None:
    """单价 × 数量属预算表那条路（`validate_budget_table` 守着）。

    这里 NEVER 顺手算一个金额：数量在 PriceCell 上，不在条目上，
    本端点手里根本没有它——**算不出的值不返回，也不填 0**。
    """
    client = _app(entries=[_entry()])

    body = _get(client, "/pricebook/pe-1").json()

    assert not [k for k in body if "amount" in k or "total" in k]
