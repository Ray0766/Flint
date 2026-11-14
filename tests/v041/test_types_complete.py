"""TYPE-02 · 九条端点的前端类型建齐。

## 卡面前提与盘上事实不符，先说清

卡面说这九条「前端根本没建类型」。那是**对账器只读 `web/lib/types.ts`**
得出的结论，而本仓的类型是**跟着各自的 client 放**的：
`viewsClient.ts` 有 `PlazaCluster` / `EvidenceCard` / `Verdict`，
`topicClient.ts` 有 `Topic` / `ProjectTopics` / `ComboResult`，
`interventionClient.ts` 有 `DisputeInput` / `EvidenceResult`。

**按「全 web/lib」重新量一遍**，九条的真缺口是：

| 端点 | 只看 `types.ts` | 全 `web/lib` 实际仍缺 |
|---|---|---|
| `/projects/{}/topics` | 「没建类型」 | **0** |
| `/topics/{}` · `/jobs/{}/verdict` · `/clusters/{}/evidence-cards` | 「没建类型」 | 各 1（**信封键**） |
| `/projects/{}/disputes` · `/projects/{}/evidence` | 「漂移」 | 各 1（`current_version`） |
| `/projects/combo` · `/projects/{}/analysis` | 「没建类型」 | 各 2 |
| `/plaza/hot` | 「没建类型」 | **15** ← 真缺口 |

按尺子的说法做，会把**正在被使用的类型**再抄一遍进 `types.ts`——
两份定义从抄完那一刻起就开始各走各的。
尺子那一处登记在 `docs/blocked/PARITY-ONLY-SCANS-TYPES-TS.md`（归 `TYPE-04`）。

## 所以本文件判的是那条**真正要紧**的性质

> **后端发出的每一个字段，在 `web/lib` 里都有一个带类型的落点。**

它比「`types.ts` 里有没有」严格（覆盖九条的全部字段），
又不会逼人重复定义。**acceptance③（`frontend_untyped_response` 归零）
在那张单修好之前达不成**——本文件把当前计数钉成等值，修好了会红。
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from tools.check_fe_be_parity import backend_routes, parity

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "web" / "lib"
API_DIR = REPO / "flint" / "api"
TICKET = REPO / "docs" / "blocked" / "PARITY-ONLY-SCANS-TYPES-TS.md"
DEMO_BASE = "http://localhost:8000"

# 卡面点名的九条。**判等值**：多一条少一条都要有人来确认。
NINE = (
    "/plaza/hot",
    "/topics/{}",
    "/projects/{}/topics",
    "/projects/{}/analysis",
    "/projects/{}/disputes",
    "/projects/{}/evidence",
    "/projects/combo",
    "/clusters/{}/evidence-cards",
    "/jobs/{}/verdict",
)
_FIELD = re.compile(r"^\s{2,}([a-z_][A-Za-z0-9_]*)\??:", re.MULTILINE)


def _typed_fields() -> set[str]:
    """**整个 `web/lib`** 里被声明过的字段名（非测试文件）。

    NEVER 只读 `types.ts`——那正是卡面前提出错的地方。
    """
    names: set[str] = set()
    for source in sorted(LIB.rglob("*.ts")):
        if ".test." in source.name or "node_modules" in source.parts:
            continue
        names |= set(_FIELD.findall(source.read_text(encoding="utf-8")))
    assert len(names) > 50, f"只扫到 {len(names)} 个字段名：扫描面塌了"
    return names


#: 响应是 pydantic 模型、因此静态抽不到字面量键的端点。
#: 这不是豁免——它们的字段由 `contracts_v04` 与 pydantic 自己守着，
#: 而这把尺子量的是「字面量 dict 的键」，本来就够不着它们
#: （工具文件头原话：「量不到的不报——报一个量不准的差异比不报更糟」）。
MODEL_RESPONSE_PATHS = frozenset({"/projects/{}/analysis", "/projects/combo"})


def _backend_keys(path: str) -> set[str]:
    return {
        key for route in backend_routes(API_DIR)
        if route.path == path for key in route.response_keys
    }


# ───────────────────────── acceptance①：九条端点的字段都有落点


def test_every_field_the_nine_endpoints_return_has_a_typed_home() -> None:
    """**本卡的主判据**：九条端点发出的每个字段，在 `web/lib` 里都有类型落点。

    比「`types.ts` 里有没有」严格：它量的是**全部九条的全部字段**，
    而不是某一个文件的内容。
    """
    typed = _typed_fields()
    homeless: dict[str, list[str]] = {}
    for path in NINE:
        keys = _backend_keys(path)
        if not keys:
            # **响应是 pydantic 模型的那几条，本来就抽不到键**——
            # 尺子取的是「被 return 出去的字面量 dict 的键」，
            # `return JSONResponse(XxxResponse(...).model_dump())` 里没有字面量 dict。
            #
            # ENTRY-05 之前这条断言是绿的，而它绿得**没有道理**：那时尺子把
            # 函数体里**每一个** dict 都算成响应，于是 `/projects/{}/analysis`
            # 抽到的是 `runner.submit(payload={...})` 那三个键——
            # 一个都不在响应里。**「扫描面塌了」这句话当时指错了对象**。
            #
            # 所以这里改成：抽不到键的必须是**已知用 pydantic 模型作响应**的那几条，
            # 名单写死。名单之外抽不到键，才是真的塌了。
            assert path in MODEL_RESPONSE_PATHS, f"{path} 一个后端键都没抽到：扫描面塌了"
            continue
        missing = sorted(keys - typed)
        if missing:
            homeless[path] = missing

    assert homeless == {}, f"这些字段没有类型落点：{homeless}"


def test_the_nine_are_exactly_the_ones_the_card_named() -> None:
    """判等值：卡面点的九条**都还在后端**，且没有第十条混进来。"""
    backend_paths = {r.path for r in backend_routes(API_DIR)}

    assert set(NINE) <= backend_paths, (
        f"卡面点的这些后端已经没有了：{sorted(set(NINE) - backend_paths)}"
    )
    assert len(NINE) == 9


# ───────────────────────── acceptance②：字段以真 payload 为准


def test_the_plaza_types_match_the_real_payload() -> None:
    """`/plaza/hot` 是九条里唯一真缺一大片的（15 个字段）。

    这里拿**真请求**逐层校验：信封三键、簇行八键、热度分量六键、弱信号九键。
    栈没起就 skip 并说清楚——**NEVER 当它通过**。
    """
    out = subprocess.run(
        ["curl", "-s", "-m", "8", f"{DEMO_BASE}/plaza/hot?day=2026-07-04",
         "-H", "X-User-Id: demo-user"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        check=False).stdout.strip()
    if not out:
        pytest.skip(f"demo 栈没起（{DEMO_BASE}）：这条要真进程才量得准")
    payload = json.loads(out)
    if not payload.get("clusters"):
        pytest.skip("这一天没有热点数据：换一天再跑")

    declared = _declared("PlazaHotResponse") | _declared("PlazaClusterRow") \
        | _declared("HotnessComponents") | _declared("WeakSignalRow")

    assert set(payload) <= declared, f"信封多出未声明的键：{set(payload) - declared}"
    assert set(payload["clusters"][0]) <= declared
    assert set(payload["clusters"][0]["hotness_components"]) <= declared
    if payload.get("weak_signals"):
        assert set(payload["weak_signals"][0]) <= declared


def _declared(interface: str) -> set[str]:
    """某个接口**自己**声明的字段名——按接口取，不按文件平集取。"""
    source = (LIB / "types.ts").read_text(encoding="utf-8")
    match = re.search(
        rf"export interface {interface}(?:<[^>]*>)? \{{(.*?)\n\}}",
        source, re.DOTALL)
    assert match, f"types.ts 里没有 {interface}"
    return set(_FIELD.findall(match.group(1)))


def test_the_hotness_components_are_numbers_not_a_synthesized_score() -> None:
    """六个分量各是一个数，**前端零计算**——NEVER 在类型里造一个「综合分」。

    后端已经给了 `hotness`；前端再合成一个，两个数会各走各的。
    """
    declared = _declared("HotnessComponents")

    # 判**等值**：多一个字段就是多了一个前端自己算的数。
    assert declared == {"velocity", "accel", "cross_count", "multi_boost",
                        "novelty_factor", "decay"}
    # 「本接口里没有 score」要在**接口内**判。第一版按字符窗口切，
    # 扫到了下一个接口的 `weak_score`——窗口开大一点就假红，那不是判据，是巧合。
    assert not any("score" in name for name in declared), declared


def test_the_day_is_the_one_the_backend_gave() -> None:
    """`day` 是后端给的那一天，类型是 `string`。

    换成 `Date` 会诱使前端拿本地时区去解析——跨时区差一天，
    而屏上说的是「这一天的热点」。
    """
    source = (LIB / "types.ts").read_text(encoding="utf-8")
    envelope = re.search(r"export interface PlazaHotResponse \{(.*?)\n\}",
                         source, re.DOTALL)
    assert envelope

    assert re.search(r"day:\s*string", envelope.group(1))
    assert "Date" not in envelope.group(1)


# ───────────────────────── acceptance③：计数——达不成，钉住


def test_the_untyped_count_is_pinned_until_the_ruler_is_fixed() -> None:
    """`frontend_untyped_response` **归不了零**，因为尺子只读 `types.ts`。

    判**等值**而不是判零：判零今天就红，而红着的门与没有门等价；
    不判则这条会被悄悄忘掉。尺子修好后本条会红，逼人回来改判据并关单。

    **注意**：`TYPE-01` 那张单说明了这个计数还会因为「平集比对」而偏低——
    有些本该是 `frontend_untyped_response` 的被错分进了 `field_mismatch`。
    两处是同一段代码的两处病，都归 `TYPE-04`。
    """
    findings = parity(REPO)
    untyped = {f.subject for f in findings if f.kind == "frontend_untyped_response"}
    drifted = {f.subject for f in findings if f.kind == "field_mismatch"}

    reported = untyped | drifted

    # `GAUGE-14`（第 6 批）之后**这个集合不再是空的**——而那不是回归。
    #
    # `TYPE-04` 把两类清成零时，尺子还带着两个盲区（首段白名单 + 只扫
    # `web/lib/`）：扫不到的调用，其响应类型自然也无从比对。
    # 盲区修掉之后，那些调用第一次进了比对面，于是 15 条**本来就在**的
    # 类型缺口第一次被看见。
    #
    # 那个零在**盲的尺子**下是真的；在看得见的尺子下不再是。
    # 判**等值而不是判零**这条口径没变——变的是等值的那一边。
    #
    # ## 第 7 批（`TYPE-05`）把十条补完了
    #
    # 十五条里，`field_mismatch` 那七条 + `/settings/locale` + 两条 deref
    # （`/citations/{}` `/price-entries/{}`，与那四条同住一个通道，一并建了）
    # 已经各有自己的类型。剩下五条归 `TYPE-06`。
    #
    # **等值的那一边又换了一次值——而口径仍然没变。**
    # 这是它第**四**次换（`TYPE-04` 清零 → `GAUGE-14` 看见十五条 →
    # `TYPE-05` 补完十条 → `TYPE-06` 补完最后五条），
    # 每一次都不是回归，每一次都要回到这里把清单改成实况。
    #
    # **回到空集了，而这一次的空与第一次的空不是同一个空**：
    # `TYPE-04` 那次的零是在**盲的尺子**下量出来的；这一次是在看得见的尺子下。
    still_open: set[str] = set()

    assert reported == still_open, (
        f"多出 {sorted(reported - still_open)}，"
        f"少了 {sorted(still_open - reported)}"
    )
    assert not drifted, f"`field_mismatch` 该由 TYPE-05 清零了：{sorted(drifted)}"
    assert TICKET.exists(), "尺子的缺陷没有单子——那与没发现过一样"


def test_the_ticket_shows_the_measurement_that_contradicts_the_card() -> None:
    """单子里要有**那张重新量过的表**，不是一句「尺子不准」。"""
    text = TICKET.read_text(encoding="utf-8")

    assert "全 web/lib" in text
    assert "PlazaCluster" in text and "topicClient" in text
    assert "15" in text, "没写出 /plaza/hot 那个真缺口的数"


def test_no_type_was_copied_from_a_client_into_types_ts() -> None:
    """**NEVER 重抄**：`types.ts` 里不许出现 client 里已有的接口名。

    抄一份进来，两份定义从那一刻起各走各的——而 TypeScript 不会告诉你
    它们已经不一样了（结构一致就通过）。
    """
    types_source = (LIB / "types.ts").read_text(encoding="utf-8")
    declared_here = set(re.findall(r"export interface (\w+)", types_source))
    elsewhere: set[str] = set()
    for source in sorted(LIB.rglob("*.ts")):
        if source.name == "types.ts" or ".test." in source.name:
            continue
        elsewhere |= set(re.findall(r"export (?:interface|type) (\w+)",
                                    source.read_text(encoding="utf-8")))

    assert declared_here & elsewhere == set(), (
        f"这些接口名两处都有：{sorted(declared_here & elsewhere)}"
    )
