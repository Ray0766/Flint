"""FB-04/FB-05：解引用端点族——把正文里的 id 换成内容。

- `GET /facts/{fact_id}`（FB-04）
- `GET /price-entries/{id}?quantity=N`（FB-05）
- `GET /citations/{citation_id}`（FB-06）
- `GET /charts/{chart_id}`（FB-07，零计算）
- `GET /cards/{card_id}` · `GET /hints/{hints_ref}`（FB-08）

## 为什么需要它

报告正文里的引用是 id：一条事实在 Block 树里存的是 `fact-demo-vecdb-cost`，而不是
「向量库托管月成本 12.5 美元」。EYE-03 的首跑截图里，用户看到的就是这些 id 本身——
前端要把它们换成内容，后端得先有地方可问。

## 三通道 NEVER 混用（S2-2 铁律之三）

`Fact` / `PriceCell` / `ProfileRef` 是**三条独立的出处通道**，各走各的端点：

- 本模块只回 Fact 通道的东西。混进一个 `amount` 或 `field_path`，
  下游就再也说不清某个数字的出处是哪条通道；
- 响应里带一个 `channel: "fact"`，让下游**读得到**自己拿的是哪条通道，
  而不是靠字段名去猜。

## 回哪一个版本

账本不可变，`facts` 按账本版本成行——同一个 `fact_id` 在 v1 与 v2 里可以是不同内容。
本端点回**该项目最新版本**那一份，并把 `ledger_version` 一并给出。
不说版本的话，两个人拿着同一个 fact_id 看到不同数字，谁都不知道差在哪。

## disputed 照实返回

`status=="disputed"` 的事实**照原样返回**并带 `disputed` 标记，NEVER 静默过滤。
悄悄滤掉一条有争议的事实，界面上留下的是一句**没有异议的结论**——那比显示争议本身危险。
（S2-4 说的是「disputed 的 fact NEVER 被新生成引用」，那管的是**生成**；
读取面把它藏起来是另一回事，且方向相反。）

## 查不到与不该看到，对外长得一样

越权取他人 fact 返回 **404 而不是 403**：403 等于告诉对方「这个 id 存在，只是不给你看」，
**状态码本身就泄露了存在性**，还能被用来枚举 id。两种情况回同一个码、同一个错误体。

## 价格通道：金额由后端算，时效照实标记，汇率不编（FB-05）

「数字必有出处」是三条铁律之一。前端自己相乘的话，屏幕上那个金额就没有出处——
它是前端算的，不进账本、不留痕、单价变了也不会告诉任何人。所以乘法在这里做完再给出去，
并把参与运算的每一项（单价区间、数量、币种、出处）一并返回，让那个金额随时能被复算。

时效走 `flint/pricebook/stale.py` 的既有口径：**过期仍可用，但必须带黄标与注记**（D13）。
用户看到一个 2023 年的单价而不知道它是 2023 年的，比看不到这个数字更糟。

币种只照实返回：K8 汇率策略未定，**NEVER 编造汇率**——编出来的那条会让整张预算表的数字
全部失去出处，而且没人看得出来。

`pricebook` 表**没有 owner 列**（全局参考数据），所以价格端点只要求身份、不按 owner 切表；
fact 端点那种按归属过滤在这里没有对应物（口径见 docs/trace/FB-05.md）。

## 只读

本模块 NEVER 写库——只有 SELECT。`tests/v041/test_deref_fact.py` 里有一个写库语句检测器
盯着这一点，并配了阴性对照（检测器对真写库语句必须报得出来，否则它的绿什么都没证明）。
"""
from __future__ import annotations

import inspect
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import asyncpg
from fastapi import FastAPI, Header, Query
from fastapi.responses import JSONResponse, Response

from flint.api.schemas import ErrorBody, ErrorCode
from flint.domain.models import PriceEntry
from flint.pricebook.stale import check_stale, price_data_notes

CHANNEL = "fact"
PRICE_CHANNEL = "price"
CITATION_CHANNEL = "citation"
CHART_CHANNEL = "chart"
CARD_CHANNEL = "evidence_card"
HINT_CHANNEL = "gap_hint"


def DEFAULT_GAP_HINTS_SOURCE(hints_ref: str) -> list[Any] | None:
    """默认取数缝：**取不到**。

    `hints_ref` 指的是 `SectionState.gap_hints`，而全库没有 `section_states` /
    `gap_hints` 表——没人存过它。所以这里如实返回 None（端点据此回 404），
    NEVER 回一个空列表：**空列表读起来是「这一节没有缺口」，那是一句结论**，
    而真相是「没人存过它」。哪天真建了表，把取数函数注进 `DerefApiDeps` 即可。
    """
    del hints_ref
    return None
DEFAULT_TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "assets" / "templates"


def _share_note() -> str:
    """私有材料的标注文案，**从冻结件 `Doc` 的 docstring 里取**，NEVER 在这里另写一句。

    冻结件原话：「导出/分享强制标注『引自用户提供材料, 外部不可核验』, 链接不外链 [审5]」。
    自己写一句的那天，导出里的说法与契约里的说法就不再是同一句，而没人会发现——
    两处都「看起来对」。取自源头就不可能漂移。
    """
    from contracts.models import Doc

    doc = inspect.getdoc(Doc) or ""
    start, end = doc.find("「"), doc.find("」")
    if start < 0 or end < 0:
        raise RuntimeError("冻结件 Doc 的 docstring 里找不到标注文案——口径变了，本处要跟着改")
    return doc[start + 1:end]

# 一次查询把「哪条 fact + 属于谁 + 哪一版」全判掉：
# 按 owner 过滤放在 SQL 里而不是取回来再判——取回来再判的写法，
# 哪天有人删掉那两行 Python 判断，数据已经出库了。
_FACT_SQL = """
SELECT f.fact_id, f.statement, f.value, f.unit, f.citation_ids, f.status, f.origin,
       f.created_in_version, f.source_claim_id, f.promoted_from,
       l.project_id, l.version AS ledger_version
FROM facts AS f
JOIN facts_ledgers AS l ON l.ledger_id = f.ledger_id
JOIN projects AS p ON p.project_id = l.project_id
WHERE f.fact_id = $1
  AND p.owner ->> 'kind' = 'user'
  AND p.owner ->> 'id' = $2
ORDER BY l.version DESC
LIMIT 1
"""


_CARD_SQL = """
SELECT e.card_id, e.cluster_id, e.keyword_ids, e.flags, e.top_links,
       c.canonical_name, c.status, c.first_seen, c.last_active
FROM evidence_cards AS e
JOIN clusters AS c ON c.cluster_id = e.cluster_id
WHERE e.card_id = $1
"""


_CITATION_SQL = """
SELECT c.citation_id, c.doc_id, c.locator, c.quote_span,
       d.title, d.url, d.kind, d.published_at, d.origin, d.access,
       d.content_sha256, d.content_truncated
FROM citations AS c
JOIN docs AS d ON d.doc_id = c.doc_id
WHERE c.citation_id = $1
"""


_PRICE_SQL = """
SELECT entry_id, item, unit, price_low, price_high, currency, region, year,
       source, updated_at, stale_after_months
FROM pricebook
WHERE entry_id = $1
"""


@dataclass
class DerefApiDeps:
    dsn: str
    # 时钟注入：时效判定要「今天」，而写死 `date.today()` 的话，
    # 「过期条目被标黄」这条断言就只能靠等日历翻页来验（等于验不了）。
    today: Callable[[], date] = date.today
    # 模板目录可注入：`ChartSpec` 只在模板里定义，而 assets/ 那四份当前全是 `charts: []`。
    # 注入让测试能造真 spec 来验，NEVER 去改 assets/ 里的模板凑数据。
    template_dir: Path = DEFAULT_TEMPLATE_DIR
    # 缺口提示的取数缝：默认取不到（见 DEFAULT_GAP_HINTS_SOURCE）。
    gap_hints_source: Callable[[str], list[Any] | None] = DEFAULT_GAP_HINTS_SOURCE


def _error(status: int, code: ErrorCode, message: str) -> JSONResponse:
    body = ErrorBody(code=code, message=message, detail=None)
    return JSONResponse(status_code=status, content=body.model_dump(exclude_none=True))


def _not_found() -> JSONResponse:
    """查不到与不该看到共用这一个响应——两者对外必须**逐字节相同**。"""
    return _error(404, "NOT_FOUND", "no such fact")


def fact_json(row: dict[str, Any]) -> dict[str, Any]:
    """行 → 响应体。字段名与冻结件 `Fact` **逐字对齐**，另加三个上下文字段。

    加的三个是 `project_id` / `ledger_version` / `channel` / `disputed`——
    它们不改冻结件的任何名字，只回答「哪一版、哪条通道、要不要提示争议」。
    """
    value = json.loads(row["value"]) if row["value"] is not None else None
    return {
        "fact_id": row["fact_id"],
        "statement": row["statement"],
        "value": value,
        "unit": row["unit"],
        "citation_ids": json.loads(row["citation_ids"]),
        "status": row["status"],
        "origin": row["origin"],
        "created_in_version": row["created_in_version"],
        "source_claim_id": row["source_claim_id"],
        "promoted_from": row["promoted_from"],
        # —— 以下非冻结件字段：上下文，不参与三通道语义 ——
        "project_id": row["project_id"],
        "ledger_version": row["ledger_version"],
        "channel": CHANNEL,
        "disputed": row["status"] == "disputed",
    }


def price_json(row: dict[str, Any], quantity: float, today: date) -> dict[str, Any]:
    """行 + 数量 → 响应体。时效判定**复用** `flint/pricebook/stale.py`。

    在这里另写一套 TTL 算法的那天，预算表上的黄标与质量卡上的注记会开始各说各的。
    币种只**照实返回**：K8 汇率策略未定，编一条汇率会让整张预算表的数字全部失去出处，
    而且没人看得出来——所以这里连一个换算字段都不给。
    """
    entry = PriceEntry(
        entry_id=row["entry_id"], item=row["item"], unit=row["unit"],
        price_low=float(row["price_low"]), price_high=float(row["price_high"]),
        currency=row["currency"], region=row["region"], year=int(row["year"]),
        source=row["source"], updated_at=row["updated_at"],
        stale_after_months=int(row["stale_after_months"]),
    )
    check = check_stale(entry, today)
    notes = price_data_notes([entry], today)
    return {
        "price_entry_id": entry.entry_id,
        "item": entry.item,
        "unit": entry.unit,
        "price_low": entry.price_low,
        "price_high": entry.price_high,
        "currency": entry.currency,
        "region": entry.region,
        "source": entry.source,
        "quantity": float(quantity),
        "amount_low": entry.price_low * quantity,
        "amount_high": entry.price_high * quantity,
        "stale": check.stale,
        "yellow_flag": check.yellow_flag,
        "price_year": check.year,
        "price_data_note": notes[0] if notes else None,
        "channel": PRICE_CHANNEL,
    }


def citation_json(row: dict[str, Any]) -> dict[str, Any]:
    """行 → 响应体。`Citation` 四字段逐字，另给文献与两条纪律位。

    **失锚（`quote_span` 为空）照实标记且照常返回**：藏起来之后，正文里那句结论
    看上去就是没有出处的——而它其实有出处，只是段落丢了。这两件事对读者的意义完全不同。

    ## DOC-03：正文的两位跟着文献一起给出去

    DOC-02 把正文落进了库（`doc_contents`），`docs` 那一行带着 `content_sha256`
    与 `content_truncated`。这两位随文献一并返回：

    - `content_sha256` —— 下游据此判断「我手上这份引文，与库里那篇是不是同一份」；
    - `content_truncated` —— **这篇正文被截断过**。引文取自被截断的正文时，
      读者有权知道「后面还有没读到的部分」。不给这一位的话，
      一条抽自半篇文章的引用与一条抽自全文的引用长得一模一样。

    **正文本身不在这里给**：这个端点回的是「一条引用」，不是「一篇文章」。
    把整篇塞进引用响应里，前端每展开一条引用就要下载一篇文章。
    正文的读取面是另一件事（登记在 DOC-03 trace §10）。
    """
    anchored = bool(row["quote_span"])
    private = row["access"] == "private"
    published = row["published_at"]
    truncated = bool(row.get("content_truncated"))
    return {
        "citation_id": row["citation_id"],
        "doc_id": row["doc_id"],
        "locator": row["locator"],
        "quote_span": row["quote_span"],
        "anchored": anchored,
        "anchor_note": None if anchored else "失锚：这条引用指着文献，但没有钉住具体段落",
        "doc": {
            "title": row["title"],
            "url": row["url"],
            "kind": row["kind"],
            "published_at": published.isoformat() if published is not None else None,
            "origin": row["origin"],
            "access": row["access"],
            # DOC-03：正文在库里的那一份的指纹与截断态（正文本身不在这里给，见 docstring）。
            "content_sha256": row.get("content_sha256"),
            "content_truncated": truncated,
            "content_note": (
                "这篇正文被截断过：后面还有没读到的部分" if truncated else None
            ),
        },
        # 审5：私有材料产品内可读，但导出/分享要标注且不外链——把依据交给下游，
        # 下游猜不出来的规则等于没有规则。
        "external_link_allowed": not private,
        "share_note": _share_note() if private else None,
        "channel": CITATION_CHANNEL,
    }


def chart_specs(template_dir: Path) -> dict[str, Any]:
    """模板目录里全部 `ChartSpec`，按 chart_id 索引。复用 `load_template`，NEVER 自己解析 yaml。"""
    from flint.compose.templates import load_template

    found: dict[str, Any] = {}
    for path in sorted(template_dir.glob("*.yaml")):
        _spec, sections = load_template(path)
        for section in sections:
            for chart in section.charts:
                found[chart.chart_id] = chart
    return found


def chart_json(spec: Any, rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """spec + 取到的 fact 行 → 响应体。**这里一个算术符号都没有。**

    每个点的 `value` 就是账本里那条的 value。端点一旦开始求和、取比例、算增长率，
    那个数字就没有出处了——它是端点算的，而端点不进账本、不留痕。
    图表是报告里最容易偷偷造数的地方，所以这条端点连一个加号都不写。

    取不到的 fact 进 `unresolved` 而不是被丢掉：**少一个点的折线图看起来完全正常**，
    没人看得出它少了一段。调用方有权知道自己拿到的是残的。
    """
    points = []
    unresolved = []
    for fact_id in spec.derived_from:
        row = rows.get(fact_id)
        if row is None:
            unresolved.append(fact_id)
            continue
        points.append({
            "fact_id": row["fact_id"],
            "statement": row["statement"],
            "value": json.loads(row["value"]) if row["value"] is not None else None,
            "unit": row["unit"],
            "citation_ids": json.loads(row["citation_ids"]),
            "status": row["status"],
            "ledger_version": row["ledger_version"],
        })
    return {
        "chart_id": spec.chart_id,
        "chart_type": spec.chart_type,
        "derived_from": list(spec.derived_from),
        "points": points,
        "unresolved": unresolved,
        "complete": not unresolved,
        "computed": False,
        "channel": CHART_CHANNEL,
    }


def card_json(row: dict[str, Any]) -> dict[str, Any]:
    """证据卡 + 它所属簇的名字。

    只给 `cluster_id` 的话，读者还要再问一次「那是哪个簇」——把簇名带上，
    一次请求就能把正文里那个 `card-2026…` 换成人话。
    """
    return {
        "card_id": row["card_id"],
        "cluster_id": row["cluster_id"],
        "keyword_ids": json.loads(row["keyword_ids"]),
        "flags": json.loads(row["flags"]),
        "top_links": json.loads(row["top_links"]),
        "cluster": {
            "canonical_name": row["canonical_name"],
            "status": row["status"],
            "first_seen": row["first_seen"].isoformat(),
            "last_active": row["last_active"].isoformat(),
        },
        "channel": CARD_CHANNEL,
    }


def _gap_why(hint: Any) -> str:
    """一条缺口「为什么算缺」的话术，**取自冻结件 `GapHint` 的 docstring**。

    冻结件原话：「missing_data → 『补充以下任一即可』+ 一键注入；
    missing_permission → 『需 {required_scope}, 你当前无权访问』→ 请 owner 授权」。
    两种缺口**修法完全不同**：一个去补资料，一个去要权限。把后者说成前者，
    用户会一直找一份根本不存在于他手里的材料——[审8] 说的
    「missing_permission 绝不伪装成缺资料」就是这个意思。

    话术从 docstring 里取而不是在这里另写：抄一份出来的，和正本迟早不是同一句。
    """
    from flint.domain.models import GapHint as _GapHint

    rule = inspect.getdoc(_GapHint) or ""
    if hint.cause == "missing_permission":
        phrase = "你当前无权访问"
        if phrase not in rule:
            raise RuntimeError("冻结件 GapHint 的权限话术变了，本处要跟着改")
        return f"需 {hint.required_scope}, {phrase}——请 owner 授权"
    phrase = "补充以下任一即可"
    if phrase not in rule:
        raise RuntimeError("冻结件 GapHint 的缺资料话术变了，本处要跟着改")
    return phrase


def hints_json(hints_ref: str, hints: list[Any]) -> dict[str, Any]:
    """缺口清单。每条都自报 `is_conclusion: false`——**缺口是缺口，不是一句站住的结论**。"""
    return {
        "hints_ref": hints_ref,
        "hints": [
            {
                "missing_what": h.missing_what,
                "cause": h.cause,
                "suggested_sources": list(h.suggested_sources),
                "action": h.action,
                "target_count": h.target_count,
                "required_scope": h.required_scope,
                "why": _gap_why(h),
                "is_conclusion": False,
            }
            for h in hints
        ],
        "is_conclusion": False,
        "channel": HINT_CHANNEL,
    }


def create_deref_app(deps: DerefApiDeps) -> FastAPI:
    app = FastAPI(title="flint-deref-api")

    @app.get("/facts/{fact_id}")
    async def fact_detail(fact_id: str, x_user_id: str = Header()) -> Response:
        conn = await asyncpg.connect(deps.dsn)
        try:
            row = await conn.fetchrow(_FACT_SQL, fact_id, x_user_id)
        finally:
            await conn.close()
        if row is None:
            return _not_found()
        return JSONResponse(status_code=200, content=fact_json(dict(row)))

    @app.get("/price-entries/{price_entry_id}")
    async def price_detail(
        price_entry_id: str,
        quantity: float = Query(gt=0),
        x_user_id: str = Header(),
    ) -> Response:
        """单价 × 数量 = 金额，**乘法在后端做**。

        前端自己相乘的话，屏幕上那个金额就没有出处——它是前端算的，不进账本、不留痕，
        单价变了也不会告诉任何人。`quantity` 必填且 > 0：默认成 1 会让「忘了传数量」
        与「真的只要一份」长得一模一样，而算出来的金额照样像个正经数字。
        """
        del x_user_id                      # 身份是入口要求；本表全局共享，不按 owner 切
        conn = await asyncpg.connect(deps.dsn)
        try:
            row = await conn.fetchrow(_PRICE_SQL, price_entry_id)
        finally:
            await conn.close()
        if row is None:
            return _error(404, "NOT_FOUND", "no such price entry")
        return JSONResponse(
            status_code=200, content=price_json(dict(row), quantity, deps.today())
        )

    @app.get("/citations/{citation_id}")
    async def citation_detail(citation_id: str, x_user_id: str = Header()) -> Response:
        del x_user_id                      # 身份是入口要求；证据层无归属列（见 trace）
        conn = await asyncpg.connect(deps.dsn)
        try:
            row = await conn.fetchrow(_CITATION_SQL, citation_id)
        finally:
            await conn.close()
        if row is None:
            return _error(404, "NOT_FOUND", "no such citation")
        return JSONResponse(status_code=200, content=citation_json(dict(row)))

    @app.get("/charts/{chart_id}")
    async def chart_detail(chart_id: str, x_user_id: str = Header()) -> Response:
        spec = chart_specs(deps.template_dir).get(chart_id)
        if spec is None:
            return _error(404, "NOT_FOUND", "no such chart")
        conn = await asyncpg.connect(deps.dsn)
        try:
            # 逐个走 fact 那条**按归属过滤**的 SQL：图表里的点与 /facts/{id} 是同一份真相，
            # 也是同一道门——换一条宽松的查询就等于给图表开了后门。
            rows = {}
            for fact_id in spec.derived_from:
                row = await conn.fetchrow(_FACT_SQL, fact_id, x_user_id)
                if row is not None:
                    rows[fact_id] = dict(row)
        finally:
            await conn.close()
        return JSONResponse(status_code=200, content=chart_json(spec, rows))

    @app.get("/cards/{card_id}")
    async def card_detail(card_id: str, x_user_id: str = Header()) -> Response:
        del x_user_id                      # 身份是入口要求；证据卡是簇级共享数据，无归属列
        conn = await asyncpg.connect(deps.dsn)
        try:
            row = await conn.fetchrow(_CARD_SQL, card_id)
        finally:
            await conn.close()
        if row is None:
            return _error(404, "NOT_FOUND", "no such evidence card")
        return JSONResponse(status_code=200, content=card_json(dict(row)))

    @app.get("/hints/{hints_ref}")
    async def hints_detail(hints_ref: str, x_user_id: str = Header()) -> Response:
        del x_user_id
        hints = deps.gap_hints_source(hints_ref)
        if hints is None:
            # NEVER 回空列表：空列表读起来是「这一节没有缺口」，那是一句结论。
            return _error(404, "NOT_FOUND", "no gap hints stored for this ref")
        return JSONResponse(status_code=200, content=hints_json(hints_ref, hints))

    return app
