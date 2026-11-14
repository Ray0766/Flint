"""SLOT-03：`translate` 作业的消费者——分派表里最后两条「没人取」之一。

## 改前

`flint/jobs/dispatch.py` 自己写着：

> `flint/i18n/name_display_job.py` 只产 payload，派生函数 `derive_name_display`
> 是同步的，**仓里还没有 translate 作业的消费者**。

提交一条 `translate`，worker 取到只会抛 `JobKindNotWired`。

## 取源与落盘为什么是**注入**的

冻结件 `contracts_v04/models_v04.py#Cluster` 在 `canonical_name` 那一行留了话：

> `canonical_name` 保留：与 `name_native` 的关系由 **REGION-04 命名规则成文**

也就是说「翻译该拿哪一段原文」**今天还没有成文**；而 `name_display` 全库没有落点
（实查：`information_schema` 里 `name_native` / `name_display` 零命中）。

这两件都不是本卡能替产品决定的。所以消费者**只做派生**，取源与落盘走注入的两个端口
——与 `DesignGenerateDeps` 把 provider 注入进来是同一个理由（那份 docstring 的原话：
「运行时用哪个模型是**注入方**的事」）。装配处没配就**大声缺**，NEVER 猜一段原文去翻。

## 判据盯着三条不能倒的既有纪律

- **B7**：原文一个字节都不能动（派生只写 display 槽）；
- **B8**：译名必带机翻标记（`translated=True` + 译者版本）；
- **A7**：翻不出来就**留空**，NEVER 用原文冒充译文——那会让 UI 拿到一个
  `translated=True` 却其实是原文的条目，B8 的标记就成了谎。
"""
from __future__ import annotations

import ast
import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
MODULE = REPO / "flint" / "jobs" / "translate.py"
NOW = datetime(2026, 8, 8, 12, 0, tzinfo=UTC)


def _cluster(cluster_id: str, native: str, display: Any = None) -> Any:
    """v0.4 冻结件的 `Cluster`（带名称三元组的那一份）。"""
    from contracts_v04.models_v04 import Cluster

    return Cluster(
        cluster_id=cluster_id, canonical_name=native, category_id="cat-ai",
        centroid=[0.0] * 1024, status="active",
        first_seen=NOW.date(), last_active=NOW.date(),
        parent_cluster_ids=[], merged_into=None, aliases=[],
        name_native=native, name_lang="zh", name_display=display,
    )


@dataclass
class _Spy:
    """记下每一次真的问了译者的 (原文, 目标语)。"""

    version: str = "spy@v1"
    asked: list[tuple[str, str]] = field(default_factory=list)
    unavailable_for: tuple[str, ...] = ()

    def translate(self, text: str, target: str) -> str:
        from flint.i18n.translator import TranslationUnavailable

        self.asked.append((text, target))
        if target in self.unavailable_for:
            raise TranslationUnavailable(f"{target} 档不可用")
        return f"[{target}]{text}"


@dataclass
class _Store:
    rows: dict[str, Any] = field(default_factory=dict)
    saved: list[str] = field(default_factory=list)

    def load(self, target_id: str) -> Any:
        return self.rows.get(target_id)

    def save(self, target_id: str, cluster: Any) -> None:
        self.rows[target_id] = cluster
        self.saved.append(target_id)


def _deps(store: _Store, spy: _Spy) -> Any:
    from flint.i18n.translator import TranslationCache
    from flint.jobs.translate import TranslateDeps

    return TranslateDeps(
        load_target=store.load, save_target=store.save,
        translator=spy, cache=TranslationCache(), now=lambda: NOW,
    )


def _blank_profile() -> Any:
    """`WorkerDeps` 要一个 profile，而本卡的执行体一个字段都不读。

    照 `tests/v041/test_design_generate_job.py` 的做法从签名生成空值：
    在判据里手抄十一个字段，冻结件加一个字段就要改一处**与本卡无关**的地方。
    """
    import inspect

    from flint.domain.models import UserProfile

    blanks = {"list": [], "dict": {}, "Mapping": {}, "int": 0,
              "float": 0.0, "bool": False}
    kwargs: dict[str, Any] = {}
    for name, param in inspect.signature(UserProfile).parameters.items():
        if param.default is not inspect.Parameter.empty:
            continue
        text = str(param.annotation)
        kwargs[name] = next(
            (v for k, v in blanks.items() if k in text), "" if "str" in text else None)
    return UserProfile(**kwargs)


def _payload(target_ids: list[str], targets: tuple[str, ...] = ("en",)) -> dict[str, Any]:
    from flint.i18n.name_display_job import translate_payload

    return translate_payload(project_id="proj-1", target_ids=target_ids, targets=targets)


def _run(job_id: str, payload: dict[str, Any], deps: Any) -> Any:
    from flint.jobs.translate import run_translate

    return asyncio.run(run_translate(job_id, payload, deps))


# ───────────────────────── 一、分派表：从「没人取」挪到「有人取」


def test_translate_is_no_longer_listed_as_unwired() -> None:
    from flint.jobs.dispatch import WIREABLE_KINDS, UnwiredKindReason

    assert "translate" in WIREABLE_KINDS, "translate 还没进已接线那一栏"
    assert "translate" not in UnwiredKindReason, (
        "两栏同时列着它——被调到时到底该抛 JobKindNotWired 还是跑起来？"
    )


def test_the_table_still_covers_the_whole_discriminated_union() -> None:
    """既有 `IncompleteDispatchTable` 判据不倒（acceptance⑤）。

    挪一条的最省事写法是「从 Unwired 里删掉」而忘了加进 WIREABLE——
    那样这条 kind 就从表里**消失**了，而 job 会回到「静默丢弃 = 永远排队」。
    """
    from flint.jobs.dispatch import (
        WIREABLE_KINDS,
        UnwiredKindReason,
        known_job_kinds,
        validate_dispatch_coverage,
    )

    declared = set(WIREABLE_KINDS) | set(UnwiredKindReason)
    validate_dispatch_coverage(declared=declared, known=set(known_job_kinds()))


def test_a_table_that_forgets_translate_still_blows_up() -> None:
    """**阴性对照**：漏掉它，`IncompleteDispatchTable` 必须响。"""
    from flint.jobs.dispatch import (
        IncompleteDispatchTable,
        known_job_kinds,
        validate_dispatch_coverage,
    )

    known = set(known_job_kinds())
    with pytest.raises(IncompleteDispatchTable, match="translate"):
        validate_dispatch_coverage(declared=known - {"translate"}, known=known)


def test_the_worker_says_what_is_missing_instead_of_pretending() -> None:
    """装配处没注入 deps 时**大声缺**，NEVER 假装跑过。

    这一条守的是「接线了」与「接线了且配齐了」的区别：
    只把 kind 挪进 WIREABLE 而不给 handler，`build_dispatch_table` 会直接拒。
    """
    from flint.jobs.worker_main import HandlerDepsMissing, WorkerDeps, build_handlers

    handlers = build_handlers(WorkerDeps(
        dsn="postgresql://unused", redis_url="redis://unused", repo_root=REPO,
        profile=_blank_profile(), now=NOW,
    ))

    with pytest.raises(HandlerDepsMissing, match="translate"):
        asyncio.run(handlers["translate"]("job-1", {}))


# ───────────────────────── 二、B7：原文一个字节都不能动


def test_the_native_name_is_never_touched() -> None:
    store = _Store(rows={"c1": _cluster("c1", "扩散模型")})
    spy = _Spy()

    _run("job-1", _payload(["c1"]), _deps(store, spy))

    assert store.rows["c1"].name_native == "扩散模型"
    assert store.rows["c1"].canonical_name == "扩散模型"


def test_the_frozen_contract_would_catch_a_rewrite() -> None:
    """**阴性对照**：冻结件自己拒绝二次赋值——本卡靠的就是它。

    没有这一条，上面那条「原文没变」可能只是因为**这一轮碰巧没人去改**。
    """
    cluster = _cluster("c1", "扩散模型")

    with pytest.raises(AttributeError, match="写一次即定"):
        cluster.name_native = "Diffusion Models"


# ───────────────────────── 三、B8：译名必带机翻标记


def test_every_derived_name_carries_the_machine_translation_mark() -> None:
    """`translated=True` + 译者版本 + 源字段。

    少了译者版本，换了模型之后旧译文会被当成新译者的产物——
    而那个标记正是 B8 让 UI 显示「机翻」的依据。
    """
    store = _Store(rows={"c1": _cluster("c1", "扩散模型")})
    spy = _Spy()

    _run("job-1", _payload(["c1"], ("en", "ja")), _deps(store, spy))

    display = store.rows["c1"].name_display
    assert set(display) == {"en", "ja"}
    for lang, value in display.items():
        assert value.translated is True, f"{lang} 没带机翻标记"
        assert value.translator == spy.version
        assert value.source_field == "name_native"
        assert value.text == f"[{lang}]扩散模型"


# ───────────────────────── 四、A7：翻不出来就留空，NEVER 拿原文冒充


def test_an_unavailable_language_is_left_empty_not_filled_with_the_original() -> None:
    store = _Store(rows={"c1": _cluster("c1", "扩散模型")})
    spy = _Spy(unavailable_for=("ja",))

    report = _run("job-1", _payload(["c1"], ("en", "ja")), _deps(store, spy))

    display = store.rows["c1"].name_display
    assert set(display) == {"en"}, "降级的那一档被写进去了"
    assert all(v.text != "扩散模型" for v in display.values()), "拿原文冒充了译文"
    assert report.degraded == 1, "降级没被数进报告——没人知道这一轮少翻了几条"


def test_a_fully_degraded_target_leaves_the_slot_none_so_the_ui_falls_back() -> None:
    """一档都没翻出来时 `name_display` 恒 `None`，UI 按 A7 退回单行。

    留一个 `{}` 的话，UI 那边 `display && …` 仍为真，
    屏上会出现一个**空的次要行**——那比单行更坏：它看起来像译文没加载出来。
    """
    store = _Store(rows={"c1": _cluster("c1", "扩散模型")})
    spy = _Spy(unavailable_for=("en",))

    _run("job-1", _payload(["c1"]), _deps(store, spy))

    assert store.rows["c1"].name_display is None


def test_degrading_never_aborts_the_rest_of_the_batch() -> None:
    """一条翻不动 NEVER 打断整批——A7 的原话是「降级不阻断」。"""
    store = _Store(rows={"c1": _cluster("c1", "甲"), "c2": _cluster("c2", "乙")})
    spy = _Spy(unavailable_for=())

    def flaky(text: str, target: str) -> str:
        from flint.i18n.translator import TranslationUnavailable

        spy.asked.append((text, target))
        if text == "甲":
            raise TranslationUnavailable("这一条不可用")
        return f"[{target}]{text}"

    spy.translate = flaky  # type: ignore[method-assign]
    report = _run("job-1", _payload(["c1", "c2"]), _deps(store, spy))

    assert store.rows["c1"].name_display is None
    assert store.rows["c2"].name_display is not None
    assert report.translated == 1 and report.degraded == 1


# ───────────────────────── 五、只补缺的那几种语言（重跑不白花钱）


def test_an_existing_translation_is_not_asked_for_again() -> None:
    from contracts_v04.models_v04 import TranslatedText

    kept = TranslatedText(text="Diffusion", translated=True,
                          translator="old@v0", source_field="name_native")
    store = _Store(rows={"c1": _cluster("c1", "扩散模型", {"en": kept})})
    spy = _Spy()

    _run("job-1", _payload(["c1"], ("en", "ja")), _deps(store, spy))

    assert [lang for _, lang in spy.asked] == ["ja"], f"重复问了译者：{spy.asked}"
    assert store.rows["c1"].name_display["en"] is kept, "既有译文被覆盖了"


# ───────────────────────── 六、缺东西时大声说，NEVER 猜


def test_a_target_that_cannot_be_loaded_is_reported_not_skipped() -> None:
    """取不到的目标进报告并点名。

    静静跳过的话，「翻完了」与「有一半根本没找到」在日志里长得一模一样。
    """
    store = _Store(rows={"c1": _cluster("c1", "扩散模型")})

    report = _run("job-1", _payload(["c1", "missing"]), _deps(store, _Spy()))

    assert report.missing == ("missing",)
    assert report.translated == 1


def test_a_payload_from_another_shape_is_rejected_loudly() -> None:
    """`source_field` 不是 `name_native` 就拒。

    冻结件把 `name_native` 定成唯一权威原文（B7）。派生管道认别的字段，
    等于开了一条「从译文再翻一次」的路。
    """
    from flint.jobs.translate import TranslatePayloadInvalid

    bad = dict(_payload(["c1"]))
    bad["source_field"] = "canonical_name"

    with pytest.raises(TranslatePayloadInvalid, match="name_native"):
        _run("job-1", bad, _deps(_Store(), _Spy()))


def test_an_empty_target_list_is_rejected() -> None:
    from flint.jobs.translate import TranslatePayloadInvalid

    with pytest.raises(TranslatePayloadInvalid):
        _run("job-1", {"project_id": "p", "target_ids": [], "targets": ["en"],
                       "source_field": "name_native"}, _deps(_Store(), _Spy()))


def test_an_empty_language_list_is_rejected() -> None:
    """一种语言都不翻的翻译作业没有意义——**它会安静地成功**，那最坏。"""
    from flint.jobs.translate import TranslatePayloadInvalid

    with pytest.raises(TranslatePayloadInvalid):
        _run("job-1", {"project_id": "p", "target_ids": ["c1"], "targets": [],
                       "source_field": "name_native"}, _deps(_Store(), _Spy()))


# ───────────────────────── 七、零真实出网


def test_the_module_opens_no_socket_of_its_own() -> None:
    """本模块 NEVER import 任何 HTTP 客户端。

    自己发的那一条会**绕过所有 respx 护栏**，而 CI 恒不联网（S2-7）。
    翻译走注入的 `Translator`：运行时是本机免费档，判据面是 fixture。
    """
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    assert not imported & {"httpx", "requests", "urllib", "http", "aiohttp", "socket"}, (
        f"消费者自己拿了个 HTTP 客户端：{sorted(imported)}"
    )


def test_a_whole_run_makes_zero_real_requests() -> None:
    """respx 护栏：整段跑完，一条真实请求都没有。

    `assert_all_mocked=True` + 零路由 ⇒ 任何一次出网当场抛。
    """
    import respx

    store = _Store(rows={"c1": _cluster("c1", "扩散模型")})

    with respx.mock(assert_all_mocked=True):
        _run("job-1", _payload(["c1"], ("en", "ja")), _deps(store, _Spy()))

    assert store.rows["c1"].name_display is not None


# ───────────────────────── 八、报告说得清这一轮到底做了什么


def test_the_report_adds_up() -> None:
    """三个数加起来等于要处理的目标数——对不上就说明有目标**无声消失**了。"""
    store = _Store(rows={"c1": _cluster("c1", "甲"), "c2": _cluster("c2", "乙")})
    spy = _Spy(unavailable_for=("en",))

    report = _run("job-1", _payload(["c1", "c2", "gone"]), _deps(store, spy))

    assert report.job_id == "job-1"
    assert report.translated + report.degraded + len(report.missing) == 3
