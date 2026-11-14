"""FB-11：前端引用的每个端点必须在后端真存在。

## 这把尺子守的是哪种病

HOTSPOT-03 那张卡的 `inputs` 里写着 `GET /clusters/{id}/verdict`——**后端从来没有这个端点**。
卡面写错不致命，**前端照着卡面写才致命**：那一屏会 404，而 404 在界面上长什么样，
取决于前端怎么处理——处理得好是「接口未提供」，处理得不好就是一片空白。

前端与后端之间没有编译期检查：一个拼错的路径、一个把 POST 写成 GET 的调用，
**在两边各自的测试里都是绿的**（前端 mock 了 fetch，后端根本不知道有人在调它）。
这条缝只能靠一把对着两边真件比对的尺子来堵。

## 判据

- **前端侧**：扫 `web/lib/` 里所有 `${base}/…` 形态的请求 URL，把 `${…}` 归一成 `{}`；
  方法从同一个调用里的 `method:` 取，取不到按 GET（`fetch` 的默认值）；
- **后端侧**：把每个 `create_*_app` 工厂真造出来，**读它的路由表**——
  不是读文档、不是读注释，是读 FastAPI 自己注册的那份；
- **对不上就红并点名**：路径不存在、或路径在而方法不允许，两种都报。

**造不出来的 app 要报出来**，NEVER 悄悄跳过：少枚举一个 app，它的路由就全变成
「后端没有」，那会造出一堆假红；反过来如果把「造不出来」当成「没有路由」处理，
真正缺的端点就藏在噪音里了。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TOOL = REPO / "tools" / "check_fe_api_contract.py"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(TOOL), *args], cwd=REPO,
                          capture_output=True, text=True, encoding="utf-8", check=False)


def _report() -> dict:
    import json

    done = _run("--json")
    assert done.stdout.strip(), done.stderr[:500]
    return json.loads(done.stdout)


# ───────────────────────── 扫描面自证


def test_the_scan_finds_the_real_clients() -> None:
    """前端侧真扫到了调用：`web/lib/` 那几个 client 都在。

    扫到 0 条也会「零不匹配」——那种绿与「全都对得上」长得一模一样（F-08 的形状）。
    """
    report = _report()
    files = {call["file"] for call in report["frontend_calls"]}

    assert len(report["frontend_calls"]) >= 10, f"只扫到 {len(report['frontend_calls'])} 条调用"
    for client in ("derefClient.ts", "jobClient.ts", "topicClient.ts",
                   "interventionClient.ts", "deliverableClient.ts"):
        assert any(client in f for f in files), f"没扫到 {client} 的调用"


def test_the_backend_route_table_comes_from_the_apps_themselves() -> None:
    """后端侧读的是 FastAPI 真注册的路由表，不是文档也不是注释。"""
    report = _report()

    assert report["backend_routes"], "一条后端路由都没枚举到"
    assert "/deliverables/{}/blocks" in report["backend_routes"]
    assert "GET" in report["backend_routes"]["/deliverables/{}/blocks"]


def test_apps_that_cannot_be_built_are_reported_not_skipped() -> None:
    """造不出来的 app **要报出来**。

    少枚举一个 app，它的路由全变成「后端没有」→ 一堆假红；
    而把「造不出来」当成「没有路由」，真正缺的端点就藏在噪音里了。
    """
    report = _report()

    assert "unbuildable_apps" in report
    assert isinstance(report["unbuildable_apps"], list)


# ───────────────────────── 正题：对得上


def test_every_frontend_call_hits_a_real_endpoint() -> None:
    """全仓：前端每一条调用都能在后端路由表里找到（路径 + 方法）。"""
    done = _run()

    assert done.returncode == 0, done.stdout + done.stderr


# ───────────────────────── 阴性对照


def test_a_call_to_a_missing_endpoint_is_red(tmp_path: Path) -> None:
    """构造一个引用不存在端点的前端文件 → 必须红并点名路径。

    **换过一次路径**：这里原先用 `/clusters/{id}/verdict`——
    当时选它正是因为它不存在（`HOTSPOT-03` 卡面点名的那条）。
    `PERSIST-04`（第 9 批）按 `DEC-044` 把它**建出来了**，
    于是这条负对照的前提当场过期：它引用的不再是一条缺失端点，
    尺子照实说「每条调用都找得到」，而判据把那句实话读成了失败。

    **红的是负对照选错了样本，不是尺子坏了。**
    换成一条**刻意合成、永远不会被建**的路径——
    NEVER 再挑一条「今天恰好还没建」的真路径当样本，
    那种样本迟早会被人建出来，而它一被建出来这条判据就又红一次。
    """
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "badClient.ts").write_text(
        'export async function v(id: string) {\n'
        '  return fetch(`${base}/clusters/${encodeURIComponent(id)}/never-built-probe`);\n'
        "}\n",
        encoding="utf-8",
    )

    done = _run("--frontend", str(lib))

    assert done.returncode == 1
    assert "/clusters/{}/never-built-probe" in done.stdout + done.stderr


def test_a_wrong_method_is_red(tmp_path: Path) -> None:
    """路径存在但方法不对也要红。

    把 POST 写成 GET，后端回 405——而 405 与 404 一样，在界面上都是「没拿到」。
    """
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "m.ts").write_text(
        'export async function lock() {\n'
        '  return fetch(`${base}/interventions/lock`, { method: "GET" });\n'
        "}\n",
        encoding="utf-8",
    )

    done = _run("--frontend", str(lib))

    assert done.returncode == 1
    assert "method" in (done.stdout + done.stderr).lower() or "GET" in done.stdout + done.stderr


def test_a_correct_call_passes(tmp_path: Path) -> None:
    """正例：写对的调用放行——见谁都报红的尺子同样量不出东西。"""
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "ok.ts").write_text(
        'export async function blocks(id: string) {\n'
        '  return fetch(`${base}/deliverables/${encodeURIComponent(id)}/blocks`);\n'
        "}\n",
        encoding="utf-8",
    )

    assert _run("--frontend", str(lib)).returncode == 0


def test_a_comment_that_mentions_a_path_is_not_read_as_a_call(tmp_path: Path) -> None:
    """**注释里写一句路径 NEVER 算一次调用**（`GAUGE-10`）。

    本文件用的这把尺子（`tools/check_fe_api_contract.py`）此前不剥注释：
    `//` 后面那对**反引号本身就长得像模板串**，于是一句解释性注释被读成真调用，
    全局门当场红。`TYPE-04` 被绊了两次，只能把注释改写成不带反引号的形状——
    **那是绕行不是修好**：一句诚实的说明性注释让门红，人学到的是「别写注释」。

    这里的注释**故意用那条真件里不存在的路径**：不剥注释的话必红。
    """
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "commented.ts").write_text(
        # 注释里那条路径同样换成**永远不会被建**的那一条：
        # 原先用 `/clusters/{}/verdict`，而 `PERSIST-04` 把它建出来了——
        # 一条**已经存在**的路径写在注释里，本来就不会被报出来，
        # 于是这条阴性对照会**恒绿**，再也拦不住「剥注释剥过头」。
        "// 说明：`/clusters/{}/never-built-probe` 在真件里不存在，这里只是提一句\n"
        "/* 块注释里也写一条：`/no/such/endpoint` */\n"
        "export async function ok() {\n"
        '  return fetch(`${base}/billing`);\n'
        "}\n",
        encoding="utf-8",
    )

    done = _run("--frontend", str(lib))

    output = done.stdout + done.stderr
    assert "/clusters/{}/never-built-probe" not in output, output
    assert "/no/such/endpoint" not in output, output
    assert done.returncode == 0, output


def test_stripping_comments_did_not_swallow_the_real_call(tmp_path: Path) -> None:
    """**阴性对照**：剥注释别把真调用一起剥了。

    剥过头时上面那条照样绿——那时尺子什么都不报，
    而「什么都没报」与「没有问题」长得一模一样。

    样本路径与上一条同因换过一次（见那条 docstring）。
    """
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "mixed.ts").write_text(
        "// 一句注释：`/billing`\n"
        "export async function bad(id: string) {\n"
        '  return fetch(`${base}/clusters/${id}/never-built-probe`);\n'
        "}\n",
        encoding="utf-8",
    )

    done = _run("--frontend", str(lib))

    assert done.returncode == 1, "真调用被连注释一起剥掉了"
    assert "/clusters/{}/never-built-probe" in done.stdout + done.stderr
