"""UIX-01 · S1 三件通用件 + 四个页面接入。

## 三态互不混用，是这张卡的全部

四种「屏上没东西」的情形，要人做的事完全不同：

| 情形 | 组件 | `data-screen-state` | 该做什么 |
|---|---|---|---|
| 请求在路上 | `LoadingSkeleton` | `loading` | 等 |
| 查过了，一条都没有 | `EmptyState` | `empty` | 去创建内容 |
| 出错了 | `ErrorState` | `failed` | 去查日志 |
| 接口没挂 / 没有后端 | `NotProvided`（既有） | `not_provided` | 去挂路由或配后端 |

混用的代价不是「不好看」，是**说了一句系统没有依据说出口的话**。

## 四个页面各自的三态在哪——不是套模板

| 页面 | 加载态 |
|---|---|
| `deliverables/[id]/export` | 已有 `pending`，换通用件 |
| `deliverables/[id]` | **async 服务器组件** → 同目录 `loading.tsx`（Next 的机制） |
| `demo` | 取数在 `DemoFlow`，补 `run()` 包壳 |
| `jobs/[id]` | SSE：`status === null` = 还没收到第一个事件 |

`deliverables/[id]` 那条是本卡最要紧的一处判断：**它的组件内部没有
「正在加载」那一刻可以渲染**。硬写一个 `if (loading)` 是一段永远进不去的死分支，
而 A6 自己的注释就写着「硬凑的死分支比没有更坏」。
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WEB = REPO / "web"
SHELL = WEB / "components" / "shell"
SCANNER = REPO / "tools" / "check_design_constraints.mjs"
TICKET = REPO / "docs" / "blocked" / "S1-COMMON-STATES-MISSING.md"

THREE = ("LoadingSkeleton", "EmptyState", "ErrorState")
WIRED_PAGES = (
    "app/deliverables/[id]/export/page.tsx",
    "app/deliverables/[id]/page.tsx",
    "app/demo/page.tsx",
    "app/jobs/[id]/page.tsx",
)


def _code(path: Path) -> str:
    text = re.sub(r"/\*[\s\S]*?\*/", "", path.read_text(encoding="utf-8"))
    return "\n".join(
        line for line in text.splitlines()
        if not line.lstrip().startswith(("//", "*"))
    )


# ───────────────────────── acceptance①：三件建出来


def test_the_three_components_exist() -> None:
    for name in THREE:
        source = SHELL / f"{name}.tsx"

        assert source.exists(), f"{name} 没建"
        assert f"export function {name}(" in source.read_text(encoding="utf-8")


def test_each_state_has_its_own_state_name() -> None:
    """**判等值**：三件各占一个 `data-screen-state`，且互不相同。

    共用一个名字，前端测试与视觉取证就分不出屏上是哪一种「没东西」。
    """
    seen = {
        name: set(re.findall(r'data-screen-state="([a-z_]+)"',
                             _code(SHELL / f"{name}.tsx")))
        for name in THREE
    }

    assert seen == {
        "LoadingSkeleton": {"loading"},
        "EmptyState": {"empty"},
        "ErrorState": {"failed"},
    }
    # 与既有的 `NotProvided` 也不许撞。
    assert "not_provided" not in set().union(*seen.values())


def test_the_empty_state_says_it_is_only_for_checked_and_really_empty() -> None:
    """`EmptyState` 的语义 MUST 写清**只用于「查过了确实为空」**。

    `WIRE-03` 登记过这条。不写清楚的话，下一个人会拿它去画「还没查」，
    而那正是本批一路在治的病。
    """
    text = (SHELL / "EmptyState.tsx").read_text(encoding="utf-8")

    assert "查过了" in text
    assert "NotProvided" in text, "没讲清它与「接口未提供」的分工"
    assert "LoadingSkeleton" in text, "没讲清它与加载态的分工"


def test_neither_state_invents_a_message() -> None:
    """两处 NEVER 由组件编：空态的 `hint`、错误态的 `detail`。

    编一句「暂无数据」或「未知错误」，既不真也没用——
    而它们会盖住调用方本来能给出的那句真话。
    """
    empty = _code(SHELL / "EmptyState.tsx")
    error = _code(SHELL / "ErrorState.tsx")

    # 不给就不画，而不是填一个默认串。
    assert "hint ?" in empty and "action ?" in empty
    assert "detail ?" in error and "onRetry ?" in error
    for text in (empty, error):
        assert "暂无" not in text and "未知" not in text


def test_the_error_state_is_announced_and_the_loading_one_is_polite() -> None:
    """故障要让读屏软件**立刻**念（`role="alert"`）；加载态只需 `aria-busy`。

    两者都不给的话，用不了眼睛的人只知道「什么都没有」。
    """
    # 判的是**属性**，不是子串：`data-role="alert"` 里也含 `role="alert"`，
    # 而那个属性对读屏软件毫无作用。变异考实测抓到的一处假绿。
    assert re.search(r'(?<![-\w])role="alert"', _code(SHELL / "ErrorState.tsx")), (
        "错误态不再向读屏软件报警了（注意 data-role 不算）"
    )
    loading = _code(SHELL / "LoadingSkeleton.tsx")
    assert 'aria-busy="true"' in loading
    assert "aria-hidden" in loading, "骨架条本身不该被念出来"


# ───────────────────────── acceptance②：四个页面接进去


def test_all_four_pages_reach_a_common_state_component() -> None:
    """四个页面**各自**够得到通用件——直接 import 或经同目录约定文件 / 本地组件。"""
    for rel in WIRED_PAGES:
        page = WEB / rel
        reachable = _code(page)
        # 同目录的 `loading.tsx` / `error.tsx`（Next 的机制）
        for name in ("loading.tsx", "error.tsx"):
            sibling = page.parent / name
            if sibling.exists():
                reachable += _code(sibling)
        # page 直接 import 的本仓组件（一层）
        for hit in re.findall(r'from "(\.[^"]+)"', _code(page)):
            target = (page.parent / f"{hit}.tsx").resolve()
            if target.exists():
                reachable += _code(target)

        assert any(name in reachable for name in THREE), f"{rel} 够不到任何通用件"


def test_the_server_component_uses_the_route_convention() -> None:
    """`deliverables/[id]` 是 async 服务器组件 → 加载态在同目录 `loading.tsx`。

    组件内部**没有「正在加载」那一刻可以渲染**。硬写一个 `if (loading)`
    是永远进不去的死分支，而死分支会让下一个人以为那屏在客户端取数。
    """
    page = _code(WEB / "app" / "deliverables" / "[id]" / "page.tsx")
    loading = WEB / "app" / "deliverables" / "[id]" / "loading.tsx"

    assert "export default async function" in page, "它不再是服务器组件了？"
    assert loading.exists(), "缺 loading.tsx——那类页面唯一诚实的加载态位置"
    body = _code(loading)
    # **Next 只认默认导出**。文件在、组件在，但不是 `export default` 的话，
    # 框架根本不会用它——而文件存在这一条判据照样绿。变异考实测抓到的一处假绿。
    assert re.search(r"export\s+default\s+function", body), (
        "loading.tsx 没有默认导出——Next 不会用它，等于没有加载态"
    )
    assert "LoadingSkeleton" in body


def test_the_demo_flow_no_longer_dies_silently_on_a_failed_request() -> None:
    """**本卡撞出的真缺陷**：`DemoFlow` 每处 `await` 都没有 `catch`。

    请求失败时 `setBusy(false)` 永远执行不到——屏幕永久停在忙碌态，
    而且一个字都不说。这不是「少了个错误提示」，是**一次失败把整屏卡死**。
    """
    flow = _code(WEB / "components" / "DemoFlow.tsx")

    assert "catch" in flow, "还是没有 catch"
    assert "finally" in flow, "没有 finally：失败时忙碌标志清不掉"
    assert "ErrorState" in flow and "LoadingSkeleton" in flow
    # 每个 handler 都要经过那层包壳，NEVER 有一条漏网。
    assert flow.count("await run(") >= 4, f"只有 {flow.count('await run(')} 处走了包壳"


def test_the_existing_assertion_surfaces_were_not_touched() -> None:
    """既有断言面**原样保留**——改样式 NEVER 顺手改断言面。"""
    export_page = _code(WEB / "app" / "deliverables" / "[id]" / "export" / "page.tsx")
    jobs_page = _code(WEB / "app" / "jobs" / "[id]" / "page.tsx")
    flow = _code(WEB / "components" / "DemoFlow.tsx")

    assert "data-export-pending" in export_page
    assert "data-demo-busy" in flow
    for marker in ("data-job-id", "data-job-status", "data-arrived-count",
                   "data-job-failed", "data-job-steps"):
        assert marker in jobs_page, marker


# ───────────────────────── acceptance③④⑤：尺子归零、登记清空


def test_the_scanner_reports_zero_violations() -> None:
    done = subprocess.run(
        ["node", str(SCANNER), str(WEB), "--json"],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", check=False)
    report = json.loads(done.stdout)

    assert report["findings"] == [], report["findings"][:4]


def test_no_rule_went_blind_while_we_made_it_green() -> None:
    """**阴性对照**：归零不能是靠让规则不落到任何文件上换来的。

    一条规则一个文件都没落到 = 它是瞎的，而瞎的与「跑过了没问题」
    在退出码上长得一模一样。
    """
    done = subprocess.run(
        ["node", str(SCANNER), str(WEB), "--json"],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", check=False)
    report = json.loads(done.stdout)
    blind = {rid for rid, count in report["applied"].items() if count == 0}
    # `noSubject` 是**对象**列表（`{"id": …, "why": …}`）——它给的是理由，
    # 不只是编号。取 id 来比；直接拿列表比会永远不等，那是一条假红。
    excused = {row["id"] for row in report.get("noSubject", [])}

    assert blind == excused, (
        f"这些规则一个文件都没落到，且不在「无可量对象」名单里：{sorted(blind - excused)}；"
        f"这些登记成「无可量对象」却其实落到了文件：{sorted(excused - blind)}"
    )
    assert report["applied"]["A6"] > 0, "A6 自己瞎了"


def test_the_known_gaps_registry_is_empty_now() -> None:
    """`KNOWN_GAPS` 清空——**留着一行都不行**。

    多一行就是「登记了一个不存在的缺口」，下一个人会去找一个已经修好的问题。
    """
    from tests.v041.test_design_constraints import KNOWN_GAPS

    assert KNOWN_GAPS == set()


def test_the_ticket_is_closed() -> None:
    text = TICKET.read_text(encoding="utf-8")
    head = "\n".join(text.splitlines()[:14])

    assert "已关闭" in head
    assert "UIX-01" in head
