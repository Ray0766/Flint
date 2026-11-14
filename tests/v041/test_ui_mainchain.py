"""UI-02：主链路四屏可点通 —— 广场 → Gate① → 报告 → 导出（含 409 阻断态）。

## 这份判据管什么，不管什么

**管**：链路接得起来（每屏都有通往下一屏的 href，且那些 href 指向真实存在的路由文件）、
错误码与后端逐字对齐、DEC-012 的归属纪律没被绕开、逐屏取证。

**不管**：渲染细节与交互分支——那是 `web/__tests__/app/mainchain.test.tsx`
（`npm test -- --run mainchain`，卡上 verify_cmd）的面。两处各判各的：
Python 这边判**契约与链路**，vitest 那边判**这一屏点下去会怎样**。

## 错误码为什么要跨语言对一遍

导出屏认的是 `EXPORT_BLOCKED` 与 `SERVICE_UNAVAILABLE` 两个字符串。
后端哪天改了枚举，前端不会报错——它只是**再也认不出 409**，于是
「有几个块挡着导出」退化成一句「导出没成功」。TypeScript 与 Python
各自的测试都看不见对面，所以这一条只能在这里判。
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WEB = REPO / "web"
APP = WEB / "app"
SMOKE = REPO / ".ui-probe" / "fe_smoke.json"
TRACE = REPO / "docs" / "trace" / "UI-02.md"
SMOKE_HARNESS = REPO / "harness" / "fe_smoke.py"

# 主链路四屏，按走的顺序。文件在盘上，路由由目录结构决定。
CHAIN = (
    ("广场", "plaza/page.tsx", "/plaza"),
    ("Gate①", "gate/[id]/page.tsx", "/gate/[id]"),
    ("报告", "deliverables/[id]/page.tsx", "/deliverables/[id]"),
    ("导出", "deliverables/[id]/export/page.tsx", "/deliverables/[id]/export"),
)
THEMES = ("dark", "light")


def _src(rel: str) -> str:
    path = APP / rel
    assert path.exists(), f"{rel} 不在盘上——链路断在这里"
    return path.read_text(encoding="utf-8")


def _node(tool: str, *args: str) -> subprocess.CompletedProcess[str]:
    node = shutil.which("node")
    assert node is not None, "找不到 node：这条门量不了，NEVER 当它通过"
    return subprocess.run([node, str(REPO / "tools" / tool), *args], cwd=REPO,
                          capture_output=True, text=True, encoding="utf-8", check=False)


# ───────────────────────── 一、四屏在盘上、且一屏接一屏（acceptance①）


def test_every_screen_of_the_chain_exists() -> None:
    for label, rel, _route in CHAIN:
        assert (APP / rel).exists(), f"{label} 屏缺 {rel}"


def test_each_screen_links_to_the_next_one() -> None:
    """每一屏都渲染出通往下一屏的 href。

    只查「文件在不在」是不够的：四个互不相连的屏也全都在盘上，
    而那不叫「可点通」。
    """
    hops = {
        "plaza/page.tsx": "/gate/",
        "gate/[id]/page.tsx": "/deliverables/",
        "deliverables/[id]/page.tsx": "/export",
    }
    for rel, target in hops.items():
        body = _src(rel)
        # 模板串里的 `${id}` 带一对花括号：把 `}` 排除在字符类外面的话，
        # `/deliverables/${id}/export` 会被截成 `/deliverables/${id`，
        # 于是判据去找一个永远找不到的后缀（实测就是这么红的一次）。
        hrefs = re.findall(r"href=\{?[`\"']([^`\"']+)", body)
        assert any(target in h for h in hrefs), f"{rel} 里没有通往 {target} 的 href：{hrefs}"


def test_the_links_point_at_routes_that_really_exist() -> None:
    """链接指向的路由要在 `web/app/` 下有 `page.tsx`——点不开的链接不算接通。"""
    routes = {route for _label, _rel, route in CHAIN}
    for route in routes:
        page = APP / route.strip("/") / "page.tsx"
        assert page.exists(), f"{route} 没有对应的 page.tsx"


def test_the_shell_can_reach_the_chain_without_an_id() -> None:
    """外壳导航里要有一条通往链路起点的无参入口，否则用户根本进不来。"""
    shell = (WEB / "components" / "shell" / "AppShell.tsx").read_text(encoding="utf-8")
    hrefs = re.findall(r'href:\s*"([^"]+)"', shell)

    assert "/plaza" in hrefs, f"导航里没有广场入口：{hrefs}"


# ───────────────────────── 二、判定归属由调用方持有（acceptance②，DEC-012）


def test_the_gate_screen_is_keyed_by_job_not_by_cluster() -> None:
    """Gate 屏按 **job** 取判定。

    判定按 job 键落在 `snapshots['snap-{job}-verdict']`；cluster→判定没有持久化真相。
    按 cluster 取就等于编造溯源链，猜错时用户会看到**另一个热点的判定**。
    """
    body = _src("gate/[id]/page.tsx")

    assert "fetchVerdict" in body, "Gate 屏没走既有的 fetchVerdict"
    assert "/clusters/" not in body, "Gate 屏按 cluster 取判定了"


def test_the_cluster_verdict_endpoint_is_called_from_exactly_one_place() -> None:
    """按热点取判定的那条端点，全仓**只在一处**被调。

    这条判据原来断言的是「全仓 NEVER 出现它——那个端点不存在」。
    **那句话在当时是对的**（`DEC-012` 乙案未开工，没有持久化真相）；
    `DEC-044` 之后 `cluster_verdicts` 就是那份真相，`PERSIST-04` 建了端点，
    `WIRE-VERDICT` 把它接上——前提没了，断言跟着翻面。

    **翻的是「有没有」，不是「几处」**：仍然只许一处（`viewsClient`）。
    第二处出现时两边会各自漂移，而屏上看不出来。
    """
    hits = []
    for path in WEB.rglob("*.ts*"):
        if "node_modules" in path.parts or "__tests__" in path.parts:
            continue
        code = "\n".join(
            ln for ln in path.read_text(encoding="utf-8", errors="replace").splitlines()
            if not ln.strip().startswith(("//", "*", "/*")))
        if re.search(r"/clusters/[^\"'`]*/verdict", code):
            hits.append(path.relative_to(WEB).as_posix())

    assert hits == ["lib/viewsClient.ts"], (
        f"按热点取判定的端点应当只在 viewsClient 里出现一次：{hits}")


def test_the_screens_only_fetch_when_the_caller_supplied_the_id() -> None:
    """缺 id 时不发请求：两屏各有一道**先判后发**的守卫。

    判的是守卫在源码里在位（渲染分支由 vitest 那边实测）。两处形态不同：
    Gate 屏是 `if (!jobId) …return`；广场屏是 `verdictJob` 为空时那条链接
    根本不渲染，于是没有任何路径去发 verdict 请求。
    """
    gate = _src("gate/[id]/page.tsx")
    plaza = _src("plaza/page.tsx")

    assert re.search(r"if\s*\(\s*!jobId\s*\)", gate), "Gate 屏缺「没有 id 就不发请求」的守卫"
    assert "fetchVerdict" not in plaza, "广场屏自己去取判定了——那条对应关系它没有"


# ───────────────────────── 三、闸门阻断说清原因与块（acceptance③）


def test_the_export_client_speaks_the_error_codes_the_backend_emits() -> None:
    """前端认的机器码与后端发的**逐字**一致。

    对不上时前端不会报错，它只是**再也认不出 409**——
    「有几个块挡着导出」退化成一句「导出没成功」。
    """
    client = (APP / "deliverables" / "[id]" / "export" / "exportClient.ts").read_text(
        encoding="utf-8")
    backend = (REPO / "flint" / "api" / "deliverables.py").read_text(encoding="utf-8")
    codes = set(re.findall(r'"(EXPORT_BLOCKED|SERVICE_UNAVAILABLE)"', client))

    assert codes == {"EXPORT_BLOCKED", "SERVICE_UNAVAILABLE"}, f"前端只认得 {sorted(codes)}"
    for code in codes:
        assert f'"{code}"' in backend, f"后端不再发 {code} 了，前端这一支成了死码"


def test_the_export_client_reads_the_detail_key_the_backend_writes() -> None:
    """`blocking_block_ids` 这个键名两边要对上——名字错了就永远读到空清单，
    而空清单在屏上看起来像「没有块被挡住」。"""
    client = (APP / "deliverables" / "[id]" / "export" / "exportClient.ts").read_text(
        encoding="utf-8")
    backend = (REPO / "flint" / "api" / "deliverables.py").read_text(encoding="utf-8")

    assert "blocking_block_ids" in client
    assert '"blocking_block_ids"' in backend


def test_the_export_screen_lists_the_blocking_blocks_not_just_a_message() -> None:
    """acceptance③：阻断时列出**被阻断的块**，NEVER 只弹一句通用报错。"""
    body = _src("deliverables/[id]/export/page.tsx")

    assert "blockingBlockIds.map" in body, "阻断态没有逐块列出来"
    assert "data-blocking-block" in body, "被阻断的块没有可取证的抓手"
    assert "export.blocked.reason" in body, "只列了 id，没说为什么被挡住"


def test_the_three_outcomes_render_differently() -> None:
    """409 / 503 / 其他失败三种结局各有各的落点，NEVER 合成一种。

    409 是用户**能自己解决**的，503 是他**等就行**的，合成一句就都变成
    「不知道该怎么办」。
    """
    body = _src("deliverables/[id]/export/page.tsx")

    for marker in ("data-export-blocked", "data-export-unavailable", "data-export-failed"):
        assert marker in body, f"少了 {marker} 这一支"


def test_the_blocking_colour_is_the_one_the_design_reserves() -> None:
    """阻断走 `--rust`（`--alert-blocking`）——蓝本色彩纪律里 rust 全站仅三处，
    409 EXPORT_BLOCKED 是其中之一。503 **不用** rust：它不是坏消息。"""
    body = _src("deliverables/[id]/export/page.tsx")
    # 按**分支判别式**切，不按 data-* 属性切：属性名互为前缀
    # （`data-export-blocked` 是 `data-export-blocked-reason` 的前缀），
    # 而 `className` 写在 `data-*` 前面，切出来的段会把隔壁分支的 class 圈进来。
    def branch(kind: str) -> str:
        start = body.find(f'outcome?.kind === "{kind}"')
        assert start != -1, f"找不到 {kind} 这一支"
        nxt = body.find("outcome?.kind ===", start + 1)
        return body[start : nxt if nxt != -1 else len(body)]

    assert "job-failed" in branch("blocked"), "阻断态没用上阻塞级那一档颜色"
    assert "job-failed" not in branch("unavailable"), "503 用了阻塞级颜色——它不是坏消息"


# ───────────────────────── 四、全程 i18n + 零脚手架（acceptance④）


def test_no_hardcoded_ui_text_in_the_new_screens() -> None:
    done = _node("i18n_scan.mjs", "web", "--fail-on-cjk")

    assert done.returncode == 0, done.stdout[-3000:] + done.stderr[-2000:]


def test_every_key_the_chain_uses_is_defined_in_both_locales() -> None:
    zh = json.loads((WEB / "messages" / "zh.json").read_text(encoding="utf-8"))
    en = json.loads((WEB / "messages" / "en.json").read_text(encoding="utf-8"))
    body = "".join(_src(rel) for _label, rel, _route in CHAIN)
    used = set(re.findall(r'(?<![\w.])t\(\s*"([^"]+)"', body))
    # 导出屏的格式名走模板 key（`export.format.${fmt}`）：模板本身正则抓不到，
    # 逐个展开来判——抓不到就当没有，那正是 F-10「按钮上写着变量名」的来路。
    used |= {f"export.format.{fmt}" for fmt in ("markdown", "html", "pdf", "docx", "pack")}

    assert used, "主链路一个 key 都没用——文案又写死回去了"
    assert used <= set(zh), f"zh.json 缺 key：{sorted(used - set(zh))}"
    assert used <= set(en), f"en.json 缺 key：{sorted(used - set(en))}"


def test_the_scaffolding_ruler_still_passes() -> None:
    """FB-10 的尺子对整个 `web/` 保持 exit 0（acceptance④ 点名）。"""
    done = _node("no_scaffold_on_screen.mjs", "web")

    assert done.returncode == 0, done.stdout + done.stderr


def test_the_chain_shows_no_endpoint_paths_on_screen() -> None:
    """端点路径 NEVER 出现在**渲染出来的文本**里（注释里提是正常的）。"""
    for label, rel, _route in CHAIN:
        code = "\n".join(ln for ln in _src(rel).splitlines()
                         if not ln.strip().startswith(("//", "*", "/*")))
        rendered = re.findall(r">\s*\{?\s*\"([^\"]{4,})\"", code)
        for text in rendered:
            assert not text.startswith("/"), f"{label} 屏上印出了路径：{text}"


# ───────────────────────── 五、逐屏取证（判 EYE-03 的产物）


def _rows() -> list[dict[str, object]]:
    assert SMOKE.exists(), "没有 .ui-probe/fe_smoke.json：起栈后跑 harness/fe_smoke.py"
    return list(json.loads(SMOKE.read_text(encoding="utf-8"))["screens"])


def test_the_new_dynamic_routes_are_registered_with_the_probe() -> None:
    """新增动态路由要登记进 `SAMPLE_IDS`——不登记的话探针把它报成 problem 并跳过，
    而跳过的正是本轮新写的屏（`harness/fe_smoke.py` 自己的注释就这么写着）。"""
    harness = SMOKE_HARNESS.read_text(encoding="utf-8")

    for route in ("/gate/[id]", "/deliverables/[id]/export"):
        assert f'"{route}"' in harness, f"{route} 没登记进 SAMPLE_IDS"


def test_the_evidence_covers_the_whole_chain_in_both_themes() -> None:
    got = {(str(r["route"]), str(r["theme"])) for r in _rows()}
    want = {(route, theme) for _l, _rel, route in CHAIN for theme in THEMES}

    assert want <= got, f"主链路取证不全，缺：{sorted(want - got)}"


def test_every_chain_screen_answers_200_without_overflow() -> None:
    chain_routes = {route for _l, _rel, route in CHAIN}
    for row in _rows():
        if row["route"] not in chain_routes:
            continue
        assert row["http_status"] == 200, f"{row['route']} [{row['theme']}] HTTP {row['http_status']}"
        assert row["horizontal_overflow"] is False, f"{row['route']} [{row['theme']}] 横向溢出"
        assert int(row["page_height"]) > 0, f"{row['route']} [{row['theme']}] 页高为 0"


def test_the_plaza_really_loaded_data_rather_than_falling_into_its_error_state() -> None:
    """广场屏必须**真的取到数**：零控制台报错，且页高远超一个错误提示的高度。

    本卡实测撞到过这个形状：起栈时环境变量名写错（`NEXT_PUBLIC_FLINT_API_BASE`
    而不是 `apiBase.ts` 真正读的 `NEXT_PUBLIC_FLINT_API`），浏览器把请求打回同源，
    `/plaza/hot` 404，屏上渲染的是错误态——**而 HTTP 状态仍是 200、也不溢出**。
    只判 200 的话，一个「读不到数据」的广场会以全绿的样子过关。
    """
    rows = [r for r in _rows() if r["route"] == "/plaza"]
    assert rows, "没有广场屏的取证"
    for row in rows:
        assert row["console_error_count"] == 0, (
            f"广场 [{row['theme']}] 有 {row['console_error_count']} 条控制台报错："
            f"{row['console_errors']}")
        assert int(row["page_height"]) > 1000, (
            f"广场 [{row['theme']}] 页高只有 {row['page_height']}px——像是错误态而不是热点列表")


def test_the_export_screen_is_quiet_until_it_is_clicked() -> None:
    """导出屏进屏时**一个请求都不发**：零控制台报错。

    进屏就试渲染的话，一次误点开会在后端跑一遍 pdf/pack 组装。
    """
    rows = [r for r in _rows() if r["route"] == "/deliverables/[id]/export"]
    assert rows, "没有导出屏的取证"
    for row in rows:
        assert row["console_error_count"] == 0, f"导出屏 [{row['theme']}] 进屏就发了请求"


def test_the_gate_screens_only_noise_is_the_honest_not_judged_404() -> None:
    """Gate 屏那条 404 是**「还没判定」本身**：REST 里 404 就是这个意思。

    判据钉住它只有这一条、且是 404——多出别的报错就说明是真出问题了。
    """
    rows = [r for r in _rows() if r["route"] == "/gate/[id]"]
    assert rows, "没有 Gate 屏的取证"
    for row in rows:
        others = [e for e in row["console_errors"] if "404" not in str(e)]  # type: ignore[union-attr]
        assert others == [], f"Gate 屏 [{row['theme']}] 出现了 404 之外的报错：{others}"
        assert int(row["console_error_count"]) <= 1, (
            f"Gate 屏 [{row['theme']}] 报错多于「未判定」那一条：{row['console_errors']}")


def test_the_two_themes_render_differently_on_every_new_screen() -> None:
    """新屏的明暗两张截图 NEVER 逐字节相同（DARK-02 的纪律）。"""
    import hashlib

    by_screen: dict[str, dict[str, str]] = {}
    for row in _rows():
        if row["route"] not in ("/plaza", "/gate/[id]", "/deliverables/[id]/export"):
            continue
        shot = SMOKE.parent / str(row["screenshot"])
        assert shot.exists(), f"截图缺失：{shot.name}"
        by_screen.setdefault(str(row["route"]), {})[str(row["theme"])] = hashlib.sha256(
            shot.read_bytes()).hexdigest()

    same = [route for route, d in by_screen.items() if len(set(d.values())) == 1]

    assert same == [], f"这些屏的明暗两张截图逐字节相同，主题没切：{same}"


# ───────────────────────── 六、trace 留档


def test_the_trace_records_the_registered_ticket_it_routed_around() -> None:
    """撞上已登记问题单要在 trace 记一行（工单 §五）。"""
    assert TRACE.exists(), "没有 docs/trace/UI-02.md"
    trace = TRACE.read_text(encoding="utf-8")

    assert "DEMO-REPORT-REFS-NOT-SEEDED" in trace
    assert "DEC-012" in trace, "trace 没写判定归属那条决定"
