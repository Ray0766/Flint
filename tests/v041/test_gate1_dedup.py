"""GATE1-DEDUP：一次分析的往返数 = 不同 URL 数。

## 实况（steward 从 `fixtures/_probe/gate1/` 的留痕里实读）

`DEC-057` 那一跑：**28 发往返 / 13 个不同 URL**；
`export.arxiv.org` 24 发、`api.github.com` 4 发；
**12 条 ×2，另有 1 条 ×4**（`all:brain-computer+interface`）。

×4 那一条说明重复是**两层叠起来**的：

| 层 | 是什么 | 结果 |
|---|---|---|
| **调用层** | `_collect_docs`（retrieve）与 `_judge_payload`（judge）**各把整个 plan 取一遍** | 每条 ×2 |
| **query 列表层** | plan 里 `support` 与 `landscape` 带**同一段检索文本** | 那条文本再 ×2 |

两层**各修各的，各判各的**（owner 逐字：NEVER 与调用层去重混成一件事）。

## 两处调用各自要什么（本卡先读清楚再动手）

| 调用点 | 它要的 | 从哪来 |
|---|---|---|
| `retrieve` | 全部文档**去重后的平铺清单** | `_flatten_docs(plan, docs_by_query)` |
| `judge` | **每条 query 各自那一份**（refute 命中率 · landscape 逐条抽竞品） | `docs_by_query` 本身 |

**两处要的不一样，但都能从同一份 `docs_by_query` 得到**——平铺清单是它的去重并集。
所以取一次，两处共享。

**NEVER 加一层缓存了事**：缓存会把「取了两次」变成「看起来取了一次」，
而两处各自要什么这件事仍然没人说得清。

## query 列表层为什么按**文本**而不是按 query 去重

`support` / `landscape` 两条 query 在判定那一侧是**两件事**（intent 不同，
judge 要分别用），而它们问上游的是**同一个问题**——
`github_search_url` / `arxiv_search_url` 只吃 `text`。

所以去重的是**取数**，不是 query 列表本身：judge 那一侧仍然看得见两条。
这条共享成立的前提（URL 只由 text 决定）由 §三 钉着。
"""
from __future__ import annotations

import collections
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from flint.domain.models import Doc, Query
from flint.evidence.search import base_meta
from flint.jobs.gate1 import (
    _fetch_docs_by_query,
    _flatten_docs,
    _plan_queries,
    build_offline_deps,
    query_id_for,
)

REPO = Path(__file__).resolve().parents[2]
PROBE = REPO / "fixtures" / "_probe" / "gate1"
NOW = datetime(2026, 8, 11, tzinfo=UTC)


@dataclass
class _CountingSearcher:
    """记下**每次被问的检索文本**——真实往返数就是这个列表的长度。

    它不发任何网络请求（`S2-7`），但它数的是与真 searcher 一一对应的东西：
    真 searcher 每被调一次就打两发（github + arxiv），
    所以「被调几次」与「打了几发」只差一个常数。
    """

    asked: list[str]

    def __call__(self, query: Query) -> list[Doc]:
        self.asked.append(query.text)
        # 字段逐字照 `flint/evidence/search.py` 里真 Doc 的构造——
        # 编一个形状不同的 Doc，红会落在 `TypeError` 上而不是被判的那件事上。
        return [Doc(doc_id=f"d-{query.text}-{i}", source_id="github", kind="repo",
                    title=f"{query.text} #{i}", url=f"https://example.test/{i}",
                    published_at=None, meta=base_meta(NOW),
                    origin="retrieved", access="public")
                for i in range(2)]


def _plan() -> list[Query]:
    return _plan_queries(build_offline_deps("postgresql://x", REPO), ["脑机接口"],
                         "zh-CN")


def _deps_with(searcher: Any) -> Any:
    deps = build_offline_deps("postgresql://x", REPO)
    return type(deps)(dsn=deps.dsn, provider=deps.provider, searcher=searcher,
                      term_map=deps.term_map, now=deps.now)


# ───────────────────────── 一、调用层：整跑只取一次


def test_one_run_asks_each_query_exactly_once() -> None:
    """**本卡的产品**：同一次分析里，**每条 query 只问上游一次**。

    ## 这条判据第一版量错了对象

    第一版写的是「往返数 MUST 等于不同 URL 数」，而那要求按**文本**共享——
    **按文本共享当场把判定改了**：`_offline_searcher` 按 `query.intent` 分支，
    `landscape` 拿到了 `support` 占住的论文而不是竞品，
    判定 `B_red_ocean` → `C_opportunity`（`tests/m2/test_m2_040` 抓住）。

    所以量的对象改成**「每条 query 恰好一次」**——对任何 `Searcher` 实现都成立。
    「同文本两条 intent 还是问了两次」那一发**是显式留下的**，
    由下一条判据钉着，单据 `GATE1-SAME-TEXT-TWO-INTENTS.md`。
    """
    plan = _plan()
    searcher = _CountingSearcher(asked=[])
    docs_by_query = _fetch_docs_by_query(_deps_with(searcher), plan)

    assert len(searcher.asked) == len(plan), (
        f"问了上游 {len(searcher.asked)} 次，而 plan 只有 {len(plan)} 条 query——"
        f"改前是 {len(plan) * 2} 次（retrieve 与 judge 各取一遍）")
    assert len(docs_by_query) == len(plan), "每条 query 都要有自己的那一份"


def test_the_call_layer_no_longer_doubles_everything() -> None:
    """**调用层那一倍真的没了**：整跑取一次，而不是 retrieve 一次 judge 一次。

    这一条量的是**基线差**：改前 `_collect_docs` 与 `_judge_payload`
    各把整个 plan 取一遍，所以是 `2 × len(plan)`。
    """
    plan = _plan()
    searcher = _CountingSearcher(asked=[])

    docs_by_query = _fetch_docs_by_query(_deps_with(searcher), plan)
    _flatten_docs(plan, docs_by_query)          # retrieve 那一份
    # judge 那一份直接用 docs_by_query，不再有第二轮取数

    assert len(searcher.asked) < 2 * len(plan), "调用层那一倍还在"
    assert len(searcher.asked) == len(plan)


def test_judge_and_retrieve_share_one_fetch() -> None:
    """retrieve 与 judge **共享同一批结果**，NEVER 各取一遍。

    判的是「`_judge_payload` 不再自己去取」——它的签名里
    `docs_by_query` 是**必填参数**，没有默认值：
    给了默认值的话，忘了传的调用点会安静地退回老路。
    """
    import inspect

    from flint.jobs.gate1 import _judge_payload

    params = inspect.signature(_judge_payload).parameters

    assert "docs_by_query" in params, "judge 又自己取数了"
    assert params["docs_by_query"].default is inspect.Parameter.empty, (
        "docs_by_query 有默认值——忘了传的调用点会安静地退回老路")


def test_the_flat_list_is_derived_not_refetched() -> None:
    """平铺清单是**从映射推出来的**，不是再取一遍。

    推出来的那一份要满足两件事：去重、保持首见顺序。
    """
    plan = _plan()
    searcher = _CountingSearcher(asked=[])
    docs_by_query = _fetch_docs_by_query(_deps_with(searcher), plan)
    before = len(searcher.asked)

    flat = _flatten_docs(plan, docs_by_query)

    assert len(searcher.asked) == before, "推平铺清单时又去问了上游"
    assert len({d.doc_id for d in flat}) == len(flat), "平铺清单里有重复"
    assert flat, "平铺清单是空的"


def test_no_call_site_keeps_its_own_copy_of_the_loop() -> None:
    """**抄本退役**：全仓 NEVER 有第二份「逐 query 取 + 按 doc_id 去重」的循环。

    `flint/revalidate/run.py` 改前自带一份——那一路因此也在取两遍。
    两处各写一份的话，去重口径哪天改了只有一处会跟上。
    """
    offenders: list[str] = []
    for path in sorted((REPO / "flint").rglob("*.py")):
        if path.name == "gate1.py" or "__pycache__" in path.parts:
            continue
        code = "\n".join(
            ln for ln in path.read_text(encoding="utf-8").splitlines()
            if not ln.strip().startswith("#"))
        if "for doc in deps.searcher(" in code:
            offenders.append(path.relative_to(REPO).as_posix())

    assert offenders == [], f"这些文件里还有一份自己的取数循环：{offenders}"


# ───────────────────────── 二、query 列表层：同一段文本只问一次


def test_the_remaining_duplicate_is_explicit_not_forgotten() -> None:
    """**第二层没有在本卡解决，而它是被写下来的，不是被忘掉的**。

    plan 里 `support` 与 `landscape` 带同一段文本（实测
    `brain-computer interface`），而 `GithubArxivSearcher` 的 URL 只吃 text——
    **同一个问题问了两遍**。

    本卡 NEVER 在 gate1 那一层按文本共享（第一版那么做，当场改了判定）。
    它要在**知道 URL 怎么算出来的那一层**解决，而那是接口改动。

    这条判据钉的是「这一发还在，且有单据」——
    没有它的话，下一个人会以为已经修干净了。
    """
    plan = _plan()
    texts = collections.Counter(q.text for q in plan)
    shared = {t: n for t, n in texts.items() if n > 1}
    assert shared, "这个 plan 里没有共享文本的 query——单据的前提没了"

    searcher = _CountingSearcher(asked=[])
    _fetch_docs_by_query(_deps_with(searcher), plan)
    asked = collections.Counter(searcher.asked)

    # 共享文本的那些**仍然**被问了不止一次——这是已知且已记录的
    assert {t: n for t, n in asked.items() if n > 1} == shared

    sheet = REPO / "docs" / "blocked" / "GATE1-SAME-TEXT-TWO-INTENTS.md"
    assert sheet.exists(), "剩下那一发没有开单"
    text = sheet.read_text(encoding="utf-8")
    assert "**状态** open" in text
    assert "B_red_ocean" in text, "单据里没写按文本共享会把判定改了"


def test_the_query_list_itself_is_not_collapsed() -> None:
    """去重的是**取数**，不是 query 列表。

    把两条 query 合并掉的话，judge 那一侧就分不出 `support` 与 `landscape`——
    而 refute 命中率与竞品抽取都按 intent 分组。
    """
    plan = _plan()
    searcher = _CountingSearcher(asked=[])
    docs_by_query = _fetch_docs_by_query(_deps_with(searcher), plan)

    assert len(docs_by_query) == len(plan)
    assert len({q.intent for q in plan}) >= 2, "plan 里只剩一种 intent 了"
    # 共享文本的那两条各自有键，且拿到的是同一批文档
    by_text: dict[str, list[str]] = {}
    for q in plan:
        by_text.setdefault(q.text, []).append(query_id_for(q))
    for text, ids in by_text.items():
        if len(ids) < 2:
            continue
        first = [d.doc_id for d in docs_by_query[ids[0]]]
        for other in ids[1:]:
            assert [d.doc_id for d in docs_by_query[other]] == first, (
                f"共享文本 {text!r} 的两条 query 拿到的文档不一样")


# ───────────────────────── 三、阴性对照：把去重摘掉 → 红且点名重复了哪条


def test_removing_the_dedup_makes_the_count_red_and_names_the_url() -> None:
    """**阴性对照**（卡面逐字）：去重摘掉 → 判据红，且**点名重复了哪条**。

    造法是把「按文本共享」那一步换成「逐 query 各问一次」，
    再拿同一条判据去量——它 MUST 说得出是哪一段文本被问了几次。
    「往返数不对」这句话对排障没有用。
    """
    plan = _plan()
    searcher = _CountingSearcher(asked=[])

    # 摘掉去重的那一版（改前 `_judge_payload` 里那三行逐字）
    for query in plan:
        searcher(query)

    asked = collections.Counter(searcher.asked)
    repeated = {t: n for t, n in asked.items() if n > 1}

    assert repeated, "摘掉去重之后居然没有重复？那说明这个 plan 里没有共享文本"
    named = " · ".join(f"{t!r}×{n}" for t, n in sorted(repeated.items()))
    assert "brain-computer interface" in named, (
        f"红了却没点名是哪一段文本重复：{named}")


def test_the_recorded_run_is_what_this_card_is_fixing() -> None:
    """留痕里那 28 发 / 13 个 URL **还在盘上**，本卡的基线不是转述。

    基线只写在 trace 里的话，下一个人无从判断「改好了」是相对什么说的。
    """
    if not PROBE.exists():
        pytest.skip("没有那一跑的留痕（`DEC-057` 窗口之外的环境）")

    urls = [json.loads(p.read_text(encoding="utf-8"))["url"]
            for p in sorted(PROBE.glob("*.json"))]
    counts = collections.Counter(urls)

    assert len(urls) > len(counts), (
        "留痕里每条 URL 只打过一次——那与本卡记录的实况对不上")
    assert max(counts.values()) >= 2


# ───────────────────────── 四、认证接缝（owner：本版不配 token）


def test_the_auth_seam_exists_and_is_empty_today() -> None:
    """`auth_headers` 这一缝**在**，且今天注进去的是**空**。

    有缝而不注：配 token 那天从这里进，不用再改一次取数代码。
    """
    import inspect

    from flint.evidence.search import GithubArxivSearcher

    params = inspect.signature(GithubArxivSearcher.__init__).parameters

    assert "auth_headers" in params, "认证接缝没了"
    assert params["auth_headers"].default is None, (
        "接缝有了默认凭据——本版不配 token")


def test_the_searcher_never_reads_an_env_var_for_credentials() -> None:
    """**NEVER 在本文件里读 env**（owner 逐字）。

    模块层读环境变量的话，「这次跑带没带凭据」就不是调用方能决定的事，
    而 CI 与本机会因为一个忘了清的变量跑出两种行为。
    """
    code = "\n".join(
        ln for ln in (REPO / "flint" / "evidence" / "search.py")
        .read_text(encoding="utf-8").splitlines()
        if not ln.strip().startswith("#"))

    for forbidden in ("os.environ", "getenv", "GITHUB_TOKEN", "api_key"):
        assert forbidden not in code, f"取数模块里出现了 {forbidden}"


def test_the_restart_conditions_are_written_where_the_seam_is() -> None:
    """什么时候回来找 owner，写在**接缝旁边**，不只写在单据里。

    只写在单据里的话，下一个改这里的人看不到它。
    """
    text = (REPO / "flint" / "evidence" / "search.py").read_text(encoding="utf-8")

    assert "第二个并发用户" in text
    assert "两位数" in text
    assert "NEVER 自行开通" in text
    assert "x-ratelimit-limit" in text, "没写那个真实数字"


def test_k1_02_carries_the_real_number() -> None:
    """K1-02 里记上今天这个真实数字（owner 逐字：NEVER 只写「额度能被收紧」）。"""
    sheet = (REPO / "docs" / "blocked" / "K1-02-SOURCE-CONTRACTS-MISSING.md"
             ).read_text(encoding="utf-8")

    assert "x-ratelimit-limit: 10" in sheet
    assert "不配" in sheet and "token" in sheet
    assert "第二个并发用户" in sheet


# ───────────────────────── 五、URL 只由文本决定（第二层去重的前提）


def test_a_searcher_may_legitimately_depend_on_intent() -> None:
    """**Searcher 是协议，不是那一个实现**——这就是不能按文本共享的理由。

    `github_search_url` / `arxiv_search_url` 只吃 text 是**那一个实现**的事；
    而 `_offline_searcher` 按 `query.intent` 分支，且那是它该做的
    （`landscape` 要竞品清单，其余要论文）。

    这条判据把「协议允许按 intent 分支」钉住：
    它成立，`_fetch_docs_by_query` 就 NEVER 能按文本共享。
    """
    from flint.jobs.gate1 import _offline_searcher

    search = _offline_searcher(fetched_at=NOW.isoformat())
    same_text = "brain-computer interface"
    # 字段逐字照冻结件 （text / source_kinds / intent / locale）——
    # 编一个形状不同的 Query，红会落在 TypeError 上而不是被判的那件事上。
    landscape = search(Query(text=same_text, source_kinds=["product"],
                             intent="landscape", locale="en-US"))
    support = search(Query(text=same_text, source_kinds=["paper"],
                           intent="support", locale="en-US"))

    assert [d.kind for d in landscape] != [d.kind for d in support], (
        "同文本不同 intent 回了同样的东西——那本卡按文本共享就没问题了，"
        "而实测它们是不同的（landscape 回 product，support 回 paper）")
