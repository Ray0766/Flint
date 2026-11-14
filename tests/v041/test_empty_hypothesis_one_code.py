"""FIX-10：同一件事（假设是空的）**一个码、一句话**。

## 改前

两条端点走的是**同一个校验器**（`flint/topic/create.py#_require_str`，
`flint/graph/store.py` 逐字写着「H8: 复用 combo 的 hypothesis 校验语义」），
抛的也是同一个异常、同一句话。**分叉只在 HTTP 映射那一层**：

```
POST /projects/combo              → 400 VALIDATION_FAILED
POST /workbenches/{id}/edges      → 422 EMPTY_HYPOTHESIS
```

规格 `#2.3` 写的是同一判据。前端于是要为同一件事写两套分支——
而写着写着必然漏掉一条，那时用户拿到的是一句通用报错，
光标不会回到假设输入框。

## 统一到哪一个

**`EMPTY_HYPOTHESIS` / 422**。`ErrorCode` 的注释逐字说明了它为什么单列：

> 「边上没写假设」与「请求体格式不对」的修法完全不同，
> 前端要据此把光标送回假设输入框而不是弹一句通用报错。

把它并回 `VALIDATION_FAILED` 就是把那句注释作废。
反过来，combo 的**其余**校验失败（卡数不对、卡不存在）**仍然是**
`VALIDATION_FAILED`——它们确实是「请求体不对」。

## 那句话怎么保证逐字一致

**从校验器身上取，NEVER 手抄。** `flint/api/errors.py` 在导入期真调一次
`_require_str({}, "hypothesis")`，把它抛出来的消息捕获下来当唯一真相。
校验器哪天改了措辞，映射与判据自动跟着走——手抄一份的话，
改了一处而另一处没改时，**判据仍然是绿的**。
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
ERRORS = REPO / "flint" / "api" / "errors.py"
COMBO = REPO / "flint" / "api" / "combo.py"
EDGES = REPO / "flint" / "api" / "graph_edges.py"
CLIENT = REPO / "web" / "lib" / "topicClient.ts"
SHEET = REPO / "docs" / "blocked" / "EMPTY-HYPOTHESIS-TWO-CODES.md"


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


# ───────────────────────── 一、那句话只有一处真相


def test_the_message_is_taken_from_the_validator_not_copied() -> None:
    """映射用的那句话**从校验器身上取**。

    手抄一份的话，改了校验器而没改映射时，**判据仍然是绿的**——
    而两条端点会开始说两句话。
    """
    from flint.api.errors import EMPTY_HYPOTHESIS_MESSAGE
    from flint.topic.create import OriginValidationError, _require_str

    with pytest.raises(OriginValidationError) as raised:
        _require_str({}, "hypothesis")

    assert EMPTY_HYPOTHESIS_MESSAGE == str(raised.value), (
        "映射里那句话与校验器真抛的不一样——它是抄的"
    )
    source = ERRORS.read_text(encoding="utf-8")
    assert "_require_str" in source, "没从校验器取，那就是手抄的"


# ───────────────────────── 二、两条端点对同一输入回同一答复


def _combo_response(hypothesis: str, card_ids: list[str]) -> Any:
    import httpx

    from flint.api.combo import ComboApiDeps, create_combo_app

    class _Provider:
        def generate(self, prompt: str, tools: Any) -> Any:
            raise AssertionError("空假设 NEVER 走到模型这一步")

        def generate_structured(self, prompt: str, schema: Any, max_retries: int) -> Any:
            raise AssertionError("空假设 NEVER 走到模型这一步")

    from datetime import UTC, datetime

    from flint.embed import DeterministicHashBackend, EmbeddingService

    app = create_combo_app(ComboApiDeps(
        dsn="postgresql://unused", provider=_Provider(),  # type: ignore[arg-type]
        embed_service=EmbeddingService(DeterministicHashBackend(dim=1024)),
        model="fixture", id_factory=lambda: "fx",
        now=lambda: datetime(2026, 8, 8, tzinfo=UTC)))

    async def go() -> Any:
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport,
                                     base_url="http://testserver") as client:
            return await client.post(
                "/projects/combo",
                json={"card_ids": card_ids, "hypothesis": hypothesis},
                headers={"x-user-id": "u-1"})

    return _run(go())


def _edge_response(hypothesis: str) -> Any:
    """边那一头。**照既有测试的做法建应用**（`tests/v04/graph/test_edge_hypothesis.py`），
    不新发明一套——两套建法迟早对不上，而那时红的会是「建法」不是「产品」。
    """
    import importlib.util
    import sys
    from datetime import UTC, datetime

    import httpx

    from flint.api.graph_edges import GraphEdgeDeps, create_graph_edge_app
    from flint.graph.store import GraphStore, add_node

    now = datetime(2026, 8, 8, tzinfo=UTC)
    spec = importlib.util.spec_from_file_location(
        "models_v04_fix10", REPO / "contracts_v04" / "models_v04.py")
    assert spec is not None and spec.loader is not None
    contract = sys.modules.get("models_v04_fix10")
    if contract is None:
        contract = importlib.util.module_from_spec(spec)
        sys.modules["models_v04_fix10"] = contract
        spec.loader.exec_module(contract)

    store = GraphStore()
    for nid in ("n-1", "n-2"):
        add_node(store, graph_id="g-1", node_id=nid, source_kind="cluster",
                 source_id=f"c-{nid}", label=nid, position=(0.0, 0.0), now=now,
                 model=contract.GraphNode)
    app = create_graph_edge_app(GraphEdgeDeps(
        store=store, now=lambda: now, edge_model=contract.GraphEdge))

    async def go() -> Any:
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport,
                                     base_url="http://testserver") as client:
            return await client.post(
                "/workbenches/g-1/edges",
                json={"edge_id": "e-1", "from_node_id": "n-1",
                      "to_node_id": "n-2", "hypothesis": hypothesis})

    return _run(go())


@pytest.mark.compose
def test_both_endpoints_answer_an_empty_hypothesis_the_same_way() -> None:
    """**本卡的核心**：同一输入 → 同一 (status, code, message)。

    只判 code 相同是不够的：两处回同一个码而消息不同，前端照样要写两套文案。
    """
    from flint.api.errors import EMPTY_HYPOTHESIS_MESSAGE

    combo = _combo_response("   ", ["card-a", "card-b"])
    edge = _edge_response("   ")

    assert (combo.status_code, combo.json()["code"]) == (422, "EMPTY_HYPOTHESIS"), (
        f"combo 那条没统一：{combo.status_code} {combo.text}"
    )
    assert (edge.status_code, edge.json()["code"]) == (422, "EMPTY_HYPOTHESIS")
    for resp in (combo, edge):
        assert resp.json()["message"] == EMPTY_HYPOTHESIS_MESSAGE, (
            f"两处话术不一致：{resp.json()['message']!r}"
        )


@pytest.mark.compose
def test_the_other_combo_failures_stay_validation_failed() -> None:
    """**阴性对照**：combo 的其余校验失败仍是 `VALIDATION_FAILED`。

    没有这一条，把整个 `OriginValidationError` 一律映成 `EMPTY_HYPOTHESIS`
    也能让上一条绿——而那时「卡数不对」会告诉用户「假设是空的」，
    光标被送到一个没有问题的输入框。
    """
    resp = _combo_response("一句真假设", ["only-one-card"])

    assert resp.status_code == 400, resp.text
    assert resp.json()["code"] == "VALIDATION_FAILED"


# ───────────────────────── 三、映射只有一处，新端点漏了会被抓


def test_neither_endpoint_maps_the_error_by_hand() -> None:
    """两条端点都**转调**同一个映射函数，NEVER 各写一个 `except` 分支。

    各写一个的后果不是重复劳动，而是**下一条端点会照着最近的那个抄**——
    而它抄到哪一个取决于作者先看到哪一份。
    """
    for path in (COMBO, EDGES):
        code = path.read_text(encoding="utf-8")
        assert "origin_validation_error" in code, f"{path.name} 没转调统一映射"
        assert not re.search(r'_error\(\s*4\d\d,\s*"EMPTY_HYPOTHESIS"', code), (
            f"{path.name} 里还手写着 EMPTY_HYPOTHESIS 的映射"
        )


def test_the_mapping_covers_every_endpoint_that_takes_a_hypothesis() -> None:
    """**扫全仓**：凡是接 `hypothesis` 的写端点，都要走这个映射。

    只判那两条的话，第三条端点漏了不会有任何东西响——
    而「新增端点漏了则判红」正是卡面 acceptance③ 要的。
    """
    api = REPO / "flint" / "api"
    offenders: list[str] = []
    for path in sorted(api.glob("*.py")):
        code = path.read_text(encoding="utf-8")
        if "OriginValidationError" not in code:
            continue
        if "origin_validation_error" not in code:
            offenders.append(path.name)

    assert offenders == [], f"这些端点接住了 OriginValidationError 却没走统一映射：{offenders}"


# ───────────────────────── 四、前端那句预检与后端**逐字**一致


def test_the_frontend_precheck_says_exactly_what_the_backend_says() -> None:
    """前端本地预检的话术与后端**逐字一致**。

    不一致的话，同一件事在「还没发出去」和「发出去被拒」两种时机上
    说两句话——用户会以为是两个问题。
    """
    from flint.api.errors import EMPTY_HYPOTHESIS_MESSAGE

    source = CLIENT.read_text(encoding="utf-8")

    assert EMPTY_HYPOTHESIS_MESSAGE in source, (
        f"前端预检没用后端那句话：库里那句是 {EMPTY_HYPOTHESIS_MESSAGE!r}"
    )
    assert "combo hypothesis is required" not in source, "旧话术还在"


def test_the_frontend_keeps_its_precheck_at_all() -> None:
    """预检**不删**：它省的是一次注定被拒的往返。

    统一话术之后最容易顺手做的事就是「反正后端会拒，前端别判了」——
    那样用户每打错一次都要等一个来回。
    """
    source = CLIENT.read_text(encoding="utf-8")

    assert 'hypothesis.trim() === ""' in source, "本地预检被删了"


# ───────────────────────── 五、单据关掉


def test_the_sheet_is_closed() -> None:
    text = SHEET.read_text(encoding="utf-8")
    state = next(ln for ln in text.splitlines()[:8] if ln.startswith("**状态**"))

    assert state.startswith("**状态** closed"), f"单据还开着：{state!r}"
    assert "FIX-10" in text


def test_the_code_list_still_explains_why_this_one_is_separate() -> None:
    """`EMPTY_HYPOTHESIS` 单列的**理由**留着。

    统一之后最容易顺手做的第二件事是把它并回 `VALIDATION_FAILED`——
    那就把「前端要把光标送回假设输入框」这条产品行为一起删了。
    """
    schemas = (REPO / "flint" / "api" / "schemas.py").read_text(encoding="utf-8")
    codes = json.loads(json.dumps(list(_error_codes())))

    assert "EMPTY_HYPOTHESIS" in codes
    assert "光标" in schemas, "那条理由的注释被删了"


def _error_codes() -> tuple[str, ...]:
    from flint.api.schemas import ERROR_CODES

    return ERROR_CODES
