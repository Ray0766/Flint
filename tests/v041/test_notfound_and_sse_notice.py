"""UIX-02 · S1 契约剩下的两件：`NotFound404` 与 `SseDisconnectNotice`。

## 两件各自在治什么

**`NotFound404`**：与「接口未提供」NEVER 用同一个表示。

| | 说的是 | 用户该做什么 | 我们该做什么 |
|---|---|---|---|
| `NotFound404` | 这个能力**在**，查了，**这一条**不存在 | 换 id / 回上层 | 什么都不用做 |
| `NotProvided` | 这个能力**还没接** | 等 | 去挂路由或配后端 |

混成一句「找不到」，用户会拿一个正确的 id 反复试；反过来混，
用户会以为自己的数据被删了。

**`SseDisconnectNotice`**：治 `WIRE-06` 实测到的那个洞——
`openJobStream` 只赋了 `onmessage`，`onerror` 从未被赋值，
`JobStreamState` 也没有一个字段能表示「连接断了」，
于是后端挂掉时屏上一个字不变，**用户把停住的旧数据读成「还在跑」**。

## 本文件最要紧的两条

1. **断线 ≠ 作业失败**：`onerror` NEVER 碰 `failedReason`；
2. **重连要能回到 `open`**：断线是可恢复态，NEVER 卡死。

第 2 条是 `WIRE-06` trace 交接下来的——它当时写着
「`UIX-02` 做的时候 MUST 带一条」。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WEB = REPO / "web"
SHELL = WEB / "components" / "shell"
CLIENT = WEB / "lib" / "jobClient.ts"
JOBS_PAGE = WEB / "app" / "jobs" / "[id]" / "page.tsx"
TICKET = REPO / "docs" / "blocked" / "SSE-DISCONNECT-IS-SILENT.md"


def _code(path: Path) -> str:
    text = re.sub(r"/\*[\s\S]*?\*/", "", path.read_text(encoding="utf-8"))
    return "\n".join(
        line for line in text.splitlines()
        if not line.lstrip().startswith(("//", "*"))
    )


# ───────────────────────── acceptance①：两件建出来


def test_both_components_exist_and_export_their_name() -> None:
    for name in ("NotFound404", "SseDisconnectNotice"):
        source = SHELL / f"{name}.tsx"

        assert source.exists(), f"{name} 没建"
        assert f"export function {name}(" in source.read_text(encoding="utf-8")


def test_the_five_s1_components_are_all_there_now() -> None:
    """S1 契约点名的**五件**，到本卡为止齐了。"""
    five = ("LoadingSkeleton", "EmptyState", "ErrorState",
            "NotFound404", "SseDisconnectNotice")

    missing = [n for n in five if not (SHELL / f"{n}.tsx").exists()]
    assert missing == [], f"S1 还缺：{missing}"


# ───────────────────────── acceptance②：404 与「接口未提供」不混


def test_not_found_and_not_provided_have_different_state_names() -> None:
    """**判等值**：两者各占一个 `data-screen-state`。

    共用一个名字，前端测试与视觉取证就分不出屏上说的是哪一件事。
    """
    not_found = set(re.findall(r'data-screen-state="([a-z_0-9]+)"',
                               _code(SHELL / "NotFound404.tsx")))
    not_provided = set(re.findall(r'data-screen-state="([a-z_0-9]+)"',
                                  _code(SHELL / "NotProvided.tsx")))

    assert not_found == {"not_found"}
    assert not_found & not_provided == set(), (
        f"两者共用了状态名：{not_found & not_provided}"
    )


def test_the_component_says_why_the_two_must_not_merge() -> None:
    """组件里要写清两者的分工——不写，下一个人就会拿它去画「接口未提供」。"""
    text = (SHELL / "NotFound404.tsx").read_text(encoding="utf-8")

    assert "NotProvided" in text
    assert "code" in text, "没讲清它对应的是**带 code 的 404**"
    # 无权与不存在共用一个表示是有意的——这条理由必须写出来，
    # 否则下一个人会「好心」把它们分开，而那是一次信息泄露。
    assert "无权" in text


def test_neither_component_invents_a_message() -> None:
    """`what` 由调用方给，`id` / `action` 不给就不画。"""
    text = _code(SHELL / "NotFound404.tsx")

    assert "id ?" in text and "action ?" in text
    assert "暂无" not in text and "未知" not in text


# ───────────────────────── acceptance③：断线态接进 jobs 屏


def test_the_stream_state_now_has_a_connection_field() -> None:
    """`JobStreamState` 有了连接态——`WIRE-06` 那个洞的正面。"""
    client = _code(CLIENT)

    assert re.search(
        r'connection:\s*"connecting"\s*\|\s*"open"\s*\|\s*"disconnected"', client)
    assert 'connection: "connecting"' in client, "初值不是 connecting"


def test_the_error_handler_is_actually_assigned() -> None:
    """`es.onerror` **被赋值了**。

    `WIRE-06` 判的是它**没**被赋值（把缺口钉成等值判据）。
    本卡是那条判据的反面——它当时写着「有人修好了就会红并指向那张单」。
    """
    client = _code(CLIENT)
    assigned = set(re.findall(r"es\.(on\w+)\s*=", client))

    assert assigned == {"onmessage", "onerror"}, assigned


def test_a_disconnect_never_touches_the_failure_reason() -> None:
    """**本卡最要紧的一条**：断线 NEVER 写进 `failedReason`。

    「作业跑挂了」是后端明确发来的 failed 事件；「我们收不到消息了」是通道的事。
    挤进同一个表示，两种完全相反的处置会显示成同一句话
    （一个去看失败原因，一个刷新页面）。
    """
    client = _code(CLIENT)
    # 切到 `es.onerror` 的**整个函数体**：按缩进找它的收尾行。
    # 第一版按 `split("};")` 切，切在了第一个 `};` 上——
    # 而 `es.close()` 写在那之后，判据看不见它（变异考实测的一处假绿）。
    body: list[str] = []
    inside = False
    for line in client.splitlines():
        if line.strip().startswith("es.onerror = "):
            inside = True
            continue
        if inside:
            if line.startswith("  };"):
                break
            body.append(line)
    handler = "\n".join(body)
    assert handler.strip(), "找不到 onerror 的函数体：扫描面塌了"

    assert "connection" in handler
    assert "failedReason" not in handler, "断线时动了 failedReason"
    # 也 NEVER 在 onerror 里 close()：原生 EventSource 正在自动重连，
    # 关掉就真断了，而屏上说的是「正在重连」。
    assert "close()" not in handler, "断线时把连接关了——那与「正在重连」矛盾"


def test_a_reconnect_returns_to_open() -> None:
    """断线是**可恢复态**：收到下一条消息要回到 `open`，NEVER 卡死。

    这条是 `WIRE-06` trace 交接下来的——它当时写着
    「`UIX-02` 做的时候 MUST 带一条」。
    """
    client = _code(CLIENT)
    handler = client.split("es.onmessage = ")[1].split("};")[0]

    assert 'connection: "open"' in handler, (
        "收到消息时没把连接态置回 open——重连成功了屏上还写着「断了」"
    )


def test_the_jobs_screen_shows_the_notice_when_disconnected() -> None:
    """屏上真的画出来，且**不藏下面的内容**。

    旧内容仍然是真的，只是可能过时了。藏起来等于把已经拿到的东西也丢掉。
    """
    page = _code(JOBS_PAGE)

    assert "SseDisconnectNotice" in page
    assert 'data-job-connection={s.connection}' in page, "断言面没给"
    assert 's.connection === "disconnected" ?' in page
    # 提示块与内容块是**并列**的两个 div，不是「二选一」。
    # 判「那一行长什么样」，不只是「那个串在不在」——
    # 把内容包进 `connection === "disconnected" ? null : …` 之后，
    # 串还在，而内容已经被藏起来了（变异考实测的一处假绿）。
    content_line = next(
        (line for line in page.splitlines() if "data-job-id={id}" in line), "")
    assert content_line.strip().startswith("<div data-job-id={id}>"), (
        f"内容块被包进了条件里：{content_line.strip()[:80]}——"
        f"旧内容仍然是真的，只是可能过时，NEVER 因为断线就藏起来"
    )


def test_the_existing_assertion_surfaces_survived() -> None:
    """原有五个断言面**一个没动**——改样式 NEVER 顺手改断言面。"""
    page = _code(JOBS_PAGE)

    for marker in ("data-job-id", "data-job-status", "data-arrived-count",
                   "data-job-failed", "data-job-steps"):
        assert marker in page, marker


def test_the_notice_is_announced_politely_not_as_an_alert() -> None:
    """断线是状态变化，不是故障：`role="status"`，NEVER `alert`。

    `alert` 会打断用户正在做的事；而这里的正确反应是「知道一下，继续等」。
    """
    text = _code(SHELL / "SseDisconnectNotice.tsx")

    assert re.search(r'(?<![-\w])role="status"', text)
    assert 'role="alert"' not in text


def test_the_ticket_is_closed() -> None:
    head = "\n".join(TICKET.read_text(encoding="utf-8").splitlines()[:16])

    assert "已关闭" in head
    assert "UIX-02" in head


def test_the_new_keys_exist_on_both_sides() -> None:
    zh = json.loads((WEB / "messages" / "zh.json").read_text(encoding="utf-8"))
    en = json.loads((WEB / "messages" / "en.json").read_text(encoding="utf-8"))

    for key in ("state.not_found", "state.disconnected", "state.disconnected_hint"):
        assert key in zh and key in en, key
        assert zh[key] != en[key], f"{key} 中英是同一个字符串"
