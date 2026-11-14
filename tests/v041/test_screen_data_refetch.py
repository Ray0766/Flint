"""UIX-05：`useScreenData` 出一个 `refetch()`，`window.location.reload()` 退役。

## 改前

钩子的签名是 `useScreenData<T>(path)`——它只在 `path` 变化时重取，
**没有别的重取入口**。第 6 批起出现「写完要重读」的屏（`ENTRY-02` 选主题第一个），
当前走的是 `window.location.reload()`：**能用、诚实，但整屏重来**
（滚动位置与屏内其它状态全丢）。

## 三条错误做法，逐条钉死

| 做法 | 为什么禁 |
|---|---|
| 前端记一份（乐观更新） | **刷新一次就没了，而用户以为自己已经选过** |
| 拿一个变化的假 query 骗重取 | 那正是 `DEC-035` 判死的形状——靠 FastAPI 静默忽略未声明 query 去实现一个副作用 |
| `reload()` | 只在**没有** `refetch` 时才可用；有了它就该退役 |

## 阴性对照是这张卡的核心

**写入后不调 `refetch`，屏上必须仍是旧值。** 没有这一条，
一个「碰巧因为别的原因也重取了」的实现会让正向判据绿——
而那时 `refetch` 有没有起作用，谁也说不出来。

判据分两层：本文件判**源码面的纪律**（谁在用、reload 退没退役、三条禁令），
`web/lib/screenDataRefetch.test.tsx` 判**运行时**（`refetch()` 真的重发请求）。
只判「函数存在」是不够的（单据原话）。
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HOOK = REPO / "web" / "lib" / "useScreenData.ts"
TOPICS = REPO / "web" / "app" / "projects" / "[id]" / "topics" / "page.tsx"
VITEST = REPO / "web" / "lib" / "screenDataRefetch.test.tsx"
SHEET = REPO / "docs" / "blocked" / "SCREEN-DATA-HOOK-HAS-NO-REFETCH.md"
WEB_APP = REPO / "web" / "app"


def _code(path: Path) -> str:
    return "\n".join(
        line for line in path.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("//"))


# ───────────────────────── 一、钩子出了句柄


def test_the_hook_returns_a_refetch_handle() -> None:
    """签名从 `Fetched<T>` 变成 `{ state, refetch }`。"""
    code = _code(HOOK)

    assert "refetch" in code, "钩子还是没有重取入口"
    assert re.search(r"state\s*:\s*Fetched<T>", code), "返回体里没有 state"


def test_the_refetch_is_stable_across_renders() -> None:
    """`refetch` **恒是同一个函数**（`useCallback`）。

    每渲染新造一个的话，把它放进任何 `useEffect` 的依赖里都会造成无限重取——
    而那个症状是「屏在疯狂打后端」，看起来像后端在被攻击。
    """
    code = _code(HOOK)

    assert "useCallback" in code, "refetch 不稳定：每次渲染都是新函数"


def test_the_hook_does_not_fake_a_query_to_force_a_refetch() -> None:
    """**NEVER 拿一个变化的假 query 骗重取**（`DEC-035` 判死的形状）。

    那是靠 FastAPI 静默忽略未声明 query 去实现一个副作用——
    而 `DEC-035` 的原话是「一个静静地什么都不筛的筛选器比没有筛选器更坏」。
    同一条：一个靠被忽略的参数工作的机制，哪天参数**不再被忽略**就当场坏掉。
    """
    code = _code(HOOK)

    for faked in ("Date.now()", "Math.random()", "_t=", "cacheBust", "nonce"):
        assert faked not in code, f"用假 query 骗重取：{faked}"


# ───────────────────────── 二、reload 退役，且没有人前端记一份


def test_the_topics_screen_uses_refetch_instead_of_reload() -> None:
    """`ENTRY-02` 那一屏改用 `refetch()`。

    `reload()` 整屏重来——滚动位置与屏内其它状态全丢。
    它当初是**唯一诚实的选择**（没有别的重取入口），现在有了。
    """
    code = _code(TOPICS)

    assert "refetch" in code, "那一屏还没改用 refetch"
    assert "location.reload" not in code, "reload 还在"


def test_no_screen_still_reloads_the_whole_page_to_refresh_data() -> None:
    """全站扫一遍：**没有一屏还靠整屏重读来刷新数据**。

    只判那一屏的话，下一个人在别的屏上又写一次 `reload()`——
    而它能用，所以不会有任何判据响。
    """
    offenders: list[str] = []
    for path in sorted(WEB_APP.rglob("*.tsx")):
        if "location.reload" in _code(path):
            offenders.append(path.relative_to(REPO).as_posix())

    assert offenders == [], "这些屏还在整屏重读：" + ", ".join(offenders)


def test_the_write_path_still_ignores_the_response_body() -> None:
    """**返回体 NEVER 被用来更新本地状态**（单据点名「加了 refetch 之后最容易破的」）。

    拿它去更新本地状态就等于在前端记了一份：**刷新一次就没了，
    而用户以为自己已经选过**。屏上显示的恒是库里那个值。
    """
    code = _code(TOPICS)
    post = code[code.index("chosen-topic"):]

    assert "res.json()" not in post, "写入路径开始读返回体了"
    assert "setState" not in post and "useState" not in post.split("return")[0], (
        "写入路径开始在前端记一份了")


# ───────────────────────── 三、运行时（vitest 实跑）


def test_the_refetch_really_refires_the_request() -> None:
    """**跑一次 vitest**：`refetch()` 真的重发请求。

    只判「函数存在」不够（单据原话）——一个空函数体照样让源码判据绿。
    那一份里还有本卡的**阴性对照**：不调 `refetch` 时屏上仍是旧值。
    """
    assert VITEST.exists(), "没有运行时判据"
    done = subprocess.run(
        ["npx", "vitest", "run", "lib/screenDataRefetch"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=REPO / "web", timeout=600, check=False, shell=True)

    assert done.returncode == 0, done.stdout[-3000:] + done.stderr[-2000:]
    assert "passed" in done.stdout


# ───────────────────────── 四、单据关掉


def test_the_sheet_is_closed() -> None:
    text = SHEET.read_text(encoding="utf-8")
    head = "\n".join(text.splitlines()[:8])

    assert "**状态** closed" in head, f"单据还开着：{head!r}"
    assert "UIX-05" in text
    assert "DEC-035" in text, "关单没记下那条「假 query」为什么禁"


def test_the_sheet_records_that_entry_01_had_nothing_to_convert() -> None:
    """单子说「`ENTRY-02` 与 `ENTRY-01` 两处改用它」——**实况是只有一处**。

    `web/app/design/page.tsx`（`ENTRY-01`）根本不用 `useScreenData`：
    它自己管提交结果，没有要重读的读态。**如实记下来**，
    否则下一个人会去找那处不存在的改动。
    """
    text = SHEET.read_text(encoding="utf-8")
    design = _code(REPO / "web" / "app" / "design" / "page.tsx")

    assert "useScreenData" not in design, "设计屏现在用上这个钩子了（本条前提变了）"
    assert "ENTRY-01" in text and "一处" in text, "单子没记下只有一处要改"
