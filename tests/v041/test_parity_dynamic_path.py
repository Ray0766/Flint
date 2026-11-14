"""TYPE-04 · 那条扫不动的动态派发路径，以及尺子的两处旧病。

## 本卡拥有 `tools/check_fe_be_parity.py`，所以三件事一起做

| 来源 | 病 |
|---|---|
| 卡面 | `/projects/${id}/${kind}` 扫不动，被记成 `dynamic_path_not_checked` |
| `TYPE-01` 登记 | 字段面**平集比对**：一个同名字段就能把「没建类型」误判成「漂移」 |
| `TYPE-02` 登记 | 字段面**只读 `types.ts`**：类型在 client 里就被报成「根本没建」 |

三处是同一段代码上的三处病，分开修第二次还要再读一遍那段逻辑。

## 结果：三类**真归零**

```
dynamic_path_not_checked   1 → 0
field_mismatch             6 → 0
frontend_untyped_response  0 → 0（此前那个零是误分类得来的）
```

**「真归零」这三个字要有依据**——所以本文件的阴性对照占一半：
每一条「现在归零了」旁边，都有一条「这样必须重新报出来」。
"""
from __future__ import annotations

import re
from pathlib import Path

from tools.check_fe_be_parity import (
    _best_interface,
    _expand_enum_segments,
    _frontend_interfaces,
    _union_members,
    _without_comments,
    frontend_calls,
    parity,
)

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "web" / "lib"
TICKETS = (
    "PARITY-FIELD-NAMES-COMPARED-AS-ONE-FLAT-SET.md",
    "PARITY-ONLY-SCANS-TYPES-TS.md",
)


# ───────────────────────── acceptance①：末段枚举展得开


def test_the_job_kind_dispatch_expands_into_three_real_paths() -> None:
    """`/projects/${id}/${kind}` 展成三条具体路径。

    `kind` 的类型是 `JobKind = "analysis" | "report" | "proposal"`，
    后端也正好有这三条 POST 路由——**这条路不是判不动，是没人去展开它**。
    """
    unions = _union_members(
        _without_comments((LIB / "jobClient.ts").read_text(encoding="utf-8")))

    assert unions.get("kind") == ("analysis", "report", "proposal")
    expanded = _expand_enum_segments("/projects/${projectId}/${kind}", unions)
    assert sorted(expanded) == [
        "/projects/${projectId}/analysis",
        "/projects/${projectId}/proposal",
        "/projects/${projectId}/report",
    ]


def test_the_three_expanded_paths_show_up_as_frontend_calls() -> None:
    """展开的结果要真的进调用面——否则展开了也没人用。"""
    # GAUGE-14：交集要拿真实路由表算，所以这里把三条一并给进去。
    calls = frontend_calls(
        REPO / "web",
        {"/projects/{}/analysis", "/projects/{}/report", "/projects/{}/proposal"})

    for path in ("/projects/{}/analysis", "/projects/{}/report",
                 "/projects/{}/proposal"):
        assert path in calls, path
    assert "/projects/{}/{}" not in calls, "还留着没展开的那条"


def test_a_path_that_really_cannot_be_resolved_stays_in_the_class() -> None:
    """**阴性对照（卡面 acceptance③）**：真判不动的仍要留在「没核对」这一类。

    变量没有字面量联合类型 → 展不开 → 原样返回一条。
    **NEVER 展不开还硬猜**：猜错了就是把「没核对」写成「核对过了」。
    """
    unions = {"kind": ("analysis", "report", "proposal")}

    # 变量名对不上任何联合类型
    assert _expand_enum_segments("/projects/${id}/${whatever}", unions) == [
        "/projects/${id}/${whatever}"]
    # 参数不在末段：中间段本来就归一成 `{}`，不是本机制的事
    assert _expand_enum_segments("/projects/${id}/topics", unions) == [
        "/projects/${id}/topics"]


def test_a_union_with_a_non_literal_member_is_not_expanded() -> None:
    """联合里只要有一个不是字符串字面量（比如 `string`），整条放弃。

    半展开比不展开更坏：它会漏掉那半条，而报告看起来是完整的。
    """
    unions = _union_members('type Loose = "a" | string;\nfoo(kind: Loose)')

    assert "kind" not in unions


# ───────────────────────── acceptance②：判不动的照旧要报出来


def test_the_dynamic_class_is_empty_now_and_the_mechanism_still_works() -> None:
    """此刻没有判不动的了；但机制还在——阴性对照证明它报得出来。"""
    dynamic = [f for f in parity(REPO) if f.kind == "dynamic_path_not_checked"]

    assert dynamic == [], f"还有扫不动的：{[f.subject for f in dynamic]}"


def test_a_comment_that_mentions_a_path_is_not_read_as_a_call() -> None:
    """注释里写的路径**不算一次调用**。

    模块 docstring 一直写着「只在字符串里找，是为了把注释排除在外」——
    **那句话此前是假的**：注释里写反引号引的路径时，那对反引号本身
    就长得像模板串。本卡给 `types.ts` 写了一句说明「这条路径此前藏在
    `/projects/{}/{}` 里」，尺子当场把它报成一条扫不动的动态路径。
    """
    text = "// 说明：`/projects/${a}/${b}` 这条以前扫不动\nconst x = 1;"

    assert "/projects" not in _without_comments(text)


def test_a_real_call_is_still_seen_after_comment_stripping() -> None:
    """阴性对照：剥注释别把真调用一起剥了。"""
    text = 'const url = `${base}/projects/${id}/topics`;  // 取主题'

    assert "/projects" in _without_comments(text)


# ───────────────────────── acceptance（登记单）：两处旧病


def test_the_field_scan_covers_every_file_in_web_lib() -> None:
    """字段面扫**整个 `web/lib`**，不是单个 `types.ts`。

    本仓的类型跟着各自 client 放；只读一个文件，会把
    `viewsClient.ts` 里的 `PlazaCluster` 报成「根本没建类型」。
    """
    interfaces = _frontend_interfaces(LIB)
    files = {name.split("#", 1)[0] for name in interfaces}

    assert len(interfaces) > 20, f"只找到 {len(interfaces)} 个接口：扫描面塌了"
    assert {"types.ts", "viewsClient.ts", "topicClient.ts"} <= files, files


def test_one_coincidental_field_name_is_not_evidence_of_a_type() -> None:
    """**平集那处病**：一个同名字段不算「建了类型」。

    `ledger_version` 撞上 disputes、`deliverable_id` 撞上 `Block`——
    都是这么来的。改后要求**至少两个字段重合**。
    """
    keys = {"alpha", "beta", "gamma", "delta"}
    interfaces = {"other.ts#Unrelated": {"alpha", "zzz", "yyy"}}

    best, covered = _best_interface(keys, interfaces)

    assert best is None, "一个同名字段就被当成了证据"
    assert covered == set()


def test_a_layered_response_is_covered_by_its_layers() -> None:
    """分层响应按**层**算覆盖面。

    后端的 `response_keys` 是摊平的：`/plaza/hot` 那 21 个键分布在
    信封 / 簇行 / 热度分量 / 弱信号四层上。要求单个接口覆盖半数以上，
    会把**分层建得好好的**响应判成「没建类型」——第一版就是这么判错的。
    """
    keys = {"day", "clusters", "rows", "a", "b", "c", "d"}
    interfaces = {
        "t.ts#Envelope": {"day", "clusters", "rows"},
        "t.ts#Row": {"a", "b", "c", "d"},
    }

    best, covered = _best_interface(keys, interfaces)

    assert best is not None
    assert keys - covered == set(), f"还缺 {keys - covered}"


def test_an_interface_with_a_stray_field_is_not_counted_as_a_layer() -> None:
    """阴性对照：**整个接口都落在响应里**才算一层。

    只要有一个字段不属于这条响应，它就不是这条响应的一层——
    放宽这一点就退回平集比对了。
    """
    keys = {"a", "b", "c", "d"}
    interfaces = {
        "t.ts#Main": {"a", "b"},
        "t.ts#Stray": {"c", "d", "not_in_this_response"},
    }

    _best, covered = _best_interface(keys, interfaces)

    assert "c" not in covered and "d" not in covered


def test_the_report_names_the_interface_it_matched() -> None:
    """报「漂移」时要**指名是哪个接口**——只说「对不上」等于把定位活退回给人。

    此刻没有漂移了，所以判的是那句话的模板还在
    （下一次真漂移时它必须报得出接口名）。
    """
    source = (REPO / "tools" / "check_fe_be_parity.py").read_text(encoding="utf-8")

    assert "前端在 {best} 里为这条端点建了类型" in source


def test_both_kinds_are_genuinely_zero_now() -> None:
    """两类**真归零**——而不是 `TYPE-02` 那次「因误分类而归零」。

    区别在于：那次 `frontend_untyped_response` 是 0 而 `field_mismatch` 是 6；
    现在两个都是 0，且尺子已经能分清它们（见上面四条对照）。
    """
    kinds = [f.kind for f in parity(REPO)]

    # `GAUGE-14`（第 6 批）之后**这两个数不再是零**——而那不是回归。
    # 修掉对账器的两个盲区之后，此前扫不到的调用第一次进了比对面，
    # 于是它们的响应类型缺口第一次被看见：7 条 `field_mismatch` +
    # 8 条 `frontend_untyped_response`。**它们一直在那儿，只是量不到。**
    #
    # 那个零在**盲的尺子**下是真的；在看得见的尺子下不再是。
    # 钉死一个过期的零，只会让下一次真正的修复被判成错。
    #
    # ## `TYPE-05` / `TYPE-06`（第 7 批）把那十五条补完了 —— **又回到零**
    #
    # 而**这一次的零与那两次的零都不是同一个零**，这条判据的名字说的正是这件事：
    #
    # | 什么时候 | 两个数 | 那个零是怎么来的 |
    # |---|---|---|
    # | `TYPE-02` | 0 / 6 | **误分类**：平集比对把「没建类型」错报成「漂移」 |
    # | `TYPE-04` | 0 / 0 | 尺子还带着两个盲区，扫不到的调用无从比对 |
    # | `GAUGE-14` | 7 / 8 | 盲区修掉，十五条**本来就在**的缺口第一次被看见 |
    # | `TYPE-05/06` | **0 / 0** | 十五条**逐条建了类型**，且尺子分得清两类 |
    #
    # 所以这里不再只判两个数——那三次的数字都对得上过某一版事实。
    # 判的是「**零 + 尺子仍然分得清**」，后半句由本文件上面那四条对照守着。
    assert kinds.count("field_mismatch") == 0
    assert kinds.count("frontend_untyped_response") == 0
    # 反向守卫：尺子没有变成什么都不报（否则上面两个零一文不值）。
    assert kinds.count("backend_unused_by_frontend") > 0


def test_the_two_registered_tickets_are_closed() -> None:
    for name in TICKETS:
        text = (REPO / "docs" / "blocked" / name).read_text(encoding="utf-8")
        head = "\n".join(text.splitlines()[:14])

        assert "已关闭" in head, name
        assert "TYPE-04" in head, name
        assert "2026-08-05" in head, name


def test_the_scanner_would_notice_a_newly_untyped_endpoint() -> None:
    """阴性对照：给一条端点加一个前端没声明的字段 → 必须重新报出来。

    没有这一条，「归零了」可能只是尺子瞎了。
    """
    keys = {"totally_new_field_a", "totally_new_field_b", "totally_new_field_c"}
    interfaces = _frontend_interfaces(LIB)

    best, covered = _best_interface(keys, interfaces)

    assert best is None, "编出来的字段居然匹配到了接口"
    assert keys - covered == keys


def test_the_module_docstring_no_longer_claims_only_types_ts() -> None:
    """模块 docstring 里那句「前端字段取自 `web/lib/types.ts`」要跟着改。

    文档与行为不一致时，下一个人会照文档去查，然后查错地方。
    """
    source = (REPO / "tools" / "check_fe_be_parity.py").read_text(encoding="utf-8")
    head = source[: source.index('"""', 3)]

    assert not re.search(r"前端字段取自\s*\n?`?web/lib/types\.ts`?\s*的接口成员", head), head[:400]
