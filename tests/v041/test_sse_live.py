"""WIRE-06 · SSE 长连接屏在装配后的栈上实测可用。

## 「装配后的 app」是哪一个——这条要先说清

`/jobs/{job_id}/events` 属 **`analysis` 族**，而那一族**没挂进
`flint/api/app.py::create_app`**：它缺 `role_resolver`（判 owner/viewer 的那只手），
凑一个 `lambda: "owner"` 上去就是人人是 owner 的安全洞
（`docs/blocked/WIRE-01-FOUR-FAMILIES-NEED-AUTH-AND-PROVIDER.md`）。

它**活在 demo 栈上**：`harness/demo_server.build_app()` 从 `create_app` 起，
再把 demo 独有的三族加上去——`lambda _u, _o: "owner"` 在 demo 里是明知故犯的口径。

所以本文件的口径是：

| 判什么 | 在哪判 |
|---|---|
| 这条路由在可部署应用上**没挂**，且**登记在案** | `create_app` |
| SSE 通道**真连一次、真收到事件** | demo 栈（真进程，`:8000`） |

**NEVER 拿 demo 栈的「通了」去说可部署应用也通了**——那是两件事。

## 断线那一半：实测是空的，已登记

`openJobStream` 只赋了 `es.onmessage`，**`onerror` 从未被赋值**；
`JobStreamState` 六个字段里没有一个能表示「连接断了」。
后端挂掉时屏上一个字都不变，用户把停住的旧数据读成「还在跑」。

修它要动 `web/lib/`，超出本卡 outputs（只有本文件）→ 停下登记：
`docs/blocked/SSE-DISCONNECT-IS-SILENT.md`。
本文件把这个缺口**钉成等值判据**：有人修好了它就会红并指向那张单。
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CLIENT = REPO / "web" / "lib" / "jobClient.ts"
HOOK = REPO / "web" / "lib" / "useJobStream.ts"
SCREEN = REPO / "web" / "app" / "jobs" / "[id]" / "page.tsx"
TICKET = REPO / "docs" / "blocked" / "SSE-DISCONNECT-IS-SILENT.md"
DEMO_BASE = "http://localhost:8000"
SSE_PATH = "/jobs/{job_id}/events"


def _code(path: Path) -> str:
    text = re.sub(r"/\*[\s\S]*?\*/", "", path.read_text(encoding="utf-8"))
    return "\n".join(
        line for line in text.splitlines()
        if not line.lstrip().startswith(("//", "*"))
    )


# ───────────────────────── 一、这条路由在哪，说清楚


def test_the_sse_route_is_not_on_the_deployable_app_and_says_so() -> None:
    """可部署应用上**没有**这条路由，且它**登记在案**。

    判等值而不是「反正 demo 有」：哪天四族接上了，本条会红，
    提醒来这里把口径改成「两边都有」。
    """
    from flint.api.app import UNWIRED_FAMILIES, create_app, mounted_route_table

    deployable = {r.path for r in mounted_route_table(
        create_app("postgresql://nobody@127.0.0.1:1/nowhere"))}
    registered = {p for family in UNWIRED_FAMILIES for p in family.paths}

    # **WIRE-07 之后这条翻面了**：analysis 族（含 SSE）已进可部署应用。
    # 原先断言的是「没挂、但登记着」；现在断言「挂上了、且不再登记为未挂」——
    # 登记与实况 MUST 一致，留着旧登记等于对账器永远报它没挂。
    assert SSE_PATH in deployable, "analysis 族已接通，SSE 该在可部署应用上"
    assert SSE_PATH not in registered, "挂上了却还登记着没挂——两个真相"


def test_the_sse_route_is_on_the_demo_stack() -> None:
    """demo 栈上有——它是本卡真连的那个。"""
    from flint.api.app import mounted_route_table
    from harness.demo_server import build_app

    assert SSE_PATH in {r.path for r in mounted_route_table(build_app())}


# ───────────────────────── acceptance①：真连一次，真收到事件


def _live_job_id() -> str:
    """从 demo 库里查一个真 job id——**NEVER 编一个**。

    `harness/fe_smoke.py` 的注释记过这个坑：首版编了个 `job-demo-fixture`，
    实跑当场现形（页面 200 但控制台一条 404）。
    """
    from harness.fe_smoke import SAMPLE_IDS

    return SAMPLE_IDS["/jobs/[id]"]


def test_the_channel_really_connects_and_delivers_at_least_one_event() -> None:
    """**真连一次**：打开 SSE，收到至少一个 `data:` 事件。

    这条 NEVER 用 mock：mock 能证明归约器对，证明不了通道通。
    栈没起就 skip 并说清楚——**NEVER 当它通过**。
    """
    url = f"{DEMO_BASE}/jobs/{_live_job_id()}/events"
    done = subprocess.run(
        ["curl", "-sN", "-m", "8", url, "-H", "X-User-Id: demo-user"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        check=False)
    body = done.stdout or ""

    if not body.strip():
        pytest.skip(f"demo 栈没起（{DEMO_BASE}）：这条要真进程才量得准，NEVER 当它通过")

    assert "data:" in body, f"连上了但一个事件都没有：{body[:200]!r}"
    payloads = [
        json.loads(line[len("data:"):].strip())
        for line in body.splitlines() if line.startswith("data:")
    ]
    assert payloads, "有 data: 行却解析不出 JSON"
    # 事件形状照 `flint/jobs/events.py` 的契约：至少带 kind。
    assert all("kind" in p for p in payloads), payloads[:2]
    # `id:` 行是断线续订用的游标，缺了就没法去重（`applyEvent` 的 seq 去重靠它）。
    assert re.search(r"^id:\s*\d+", body, re.MULTILINE), "没有 id: 行，断线续订会重复挂载"


def test_the_screen_subscribes_through_the_hook_not_its_own_fetch() -> None:
    """屏走 `useJobStream`，**不自己发请求**——两条路会各自维护一份状态。"""
    code = _code(SCREEN)

    assert "useJobStream(" in code
    assert "fetch(" not in code and "EventSource(" not in code


# ───────────────────────── acceptance②：断线态——实测是空的，钉住


def test_the_disconnect_state_exists_now() -> None:
    """断线那一半**做了**（`UIX-02`），本条随之从「钉缺口」翻成正面断言。

    ## 这条判据换了一次，而那次换是设计好的

    `WIRE-06` 写它时判的是**等值**：处理器集 == `{onmessage}` 且无连接态字段，
    并在失败信息里逐字写着「若是补上了 onerror，去关单并把本条改成断言断线态存在」。
    `UIX-02` 补上之后它当场变红，照那句话改成了现在这样。

    **这比留一个 TODO 强的地方就在这里：TODO 不会红，也不会告诉你怎么改。**

    断线态本身的细节判据在 `tests/v041/test_notfound_and_sse_notice.py`
    （不碰 `failedReason` / 不 `close()` / 重连回到 `open`）。
    """
    client = _code(CLIENT)
    assigned = set(re.findall(r"es\.(on\w+)\s*=", client))
    fields = set(re.findall(r"^\s{2}(\w+):", client, re.MULTILINE))

    assert assigned == {"onmessage", "onerror"}, sorted(assigned)
    assert "connection" in fields, "连接态字段又没了？"
    head = TICKET.read_text(encoding="utf-8").splitlines()[:16]
    assert any("已关闭" in line for line in head), "断线态做了，单子却还挂着"


def test_the_ticket_spells_out_the_fix_and_who_does_it() -> None:
    """单子要给**可执行的修法**与责任人，不是一句「有问题」。"""
    text = TICKET.read_text(encoding="utf-8")

    assert "onerror" in text
    assert "UIX-02" in text, "没说谁来做"
    assert "failedReason" in text, (
        "没讲清「作业失败」与「连接断了」是两件事——那是这张单最容易混的一处"
    )


def test_job_failure_and_connection_loss_are_two_different_fields() -> None:
    """**`failedReason` NEVER 兼职断线态**。

    「作业跑挂了」是后端明确发的 failed 事件；「我们收不到消息了」是通道的事。
    挤进同一个表示，两种完全不同的处置会显示成同一句话。

    本条守的是**修的时候别走这条捷径**——现在它是绿的，
    因为 `failedReason` 只在 failed 事件里被赋值。
    """
    client = _code(CLIENT)
    # 真赋值长这样：`next.failedReason = payload.reason;`
    # 第一版只扫 `failedReason:\s*(...)`，那只看得见**类型声明与初值**——
    # 变异考当场证明它抓不住任何真改动。扫描面写窄了，判据就是空的。
    assignments = re.findall(r"\.failedReason\s*=\s*([^;\n]+)", client)

    assert assignments, "找不到 failedReason 的赋值：扫描面塌了"
    for value in assignments:
        text = value.strip()
        # ① 只能来自**服务端发来的那条消息**（`payload.*`）。
        assert text.startswith("payload."), (
            f"failedReason 的值不是从服务端事件来的：{text!r}——"
            f"「作业跑挂了」与「我们收不到消息了」NEVER 挤进同一个字段"
        )
        # ② **不许给它编一个兜底理由**。`payload.reason ?? "连接断开"` 这种写法
        # 以 `payload.` 开头，第一版判据放它过去了（变异考实测）——
        # 而它正是把断线伪装成作业失败的最短路径：服务端没给理由，前端替它编一个。
        assert not re.search(r"\?\?|\|\|", text), (
            f"failedReason 有兜底值：{text!r}——服务端没给理由时就是没有，"
            f"NEVER 替它编一个"
        )


def test_the_hook_resubscribes_only_on_job_id_change() -> None:
    """重复订阅会造出两条通道，事件到达两次——`applyEvent` 的 seq 去重挡得住
    重放，挡不住两条独立连接各发一份。"""
    hook = _code(HOOK)

    assert "[jobId]" in hook, "依赖数组不是只看 jobId"
