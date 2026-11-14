"""FIX-04 · 间歇红：先证因，后修。

## 「重跑一遍就好」是要治的病本身

一条用例 5 次里红 1 次，单独跑恒绿。这种红比稳定红更坏：
它训练人「重跑一遍就好」，而那个习惯会让下一次真缺陷也被重跑掉。

## 先连跑 10 次（acceptance①）

**没红**（10 次全绿，754 passed × 10）。所以观察本身没有把因指出来——
到这一步为止，**唯一诚实的结论是「这 10 次没复现」**，
NEVER 由此写成「修好了」或「本来就没问题」。

## 再把嫌疑面逐个证伪 / 证实

单子怀疑的是 `vi.stubGlobal` 跨用例不还原。清点属实：
十个文件 stub 同一个 `fetch`，**没有任何一个文件还原**。
但那不是这次的因——vitest 默认按文件隔离环境，跨文件传不过去。

真正的因在 `ui07.test.tsx#renderLoadedPage`：它 `waitFor(下拉存在)` 就返回，
而屏上到位要**两拍**——第一拍数据 ready、下拉渲染出来（草稿仍是默认 zh/CN），
第二拍对齐草稿的 effect 冲刷、值才变成后端给的那个。
断言值的那条用例在两拍之间抢跑。

**这条是实测出来的**：把那个等法放进 40 次循环，第 29 次抓到 `zh`。
默认值那条用例看不出来，因为 zh/CN 恰好就是它的期望值。

## 两件事都做，但分得清

| | 做了什么 | 是不是那次红的因 |
|---|---|---|
| `renderLoadedPage` | 等的是**值**不是元素存在 | **是** |
| `unstubGlobals: true` | 每条用例跑完还原全局 | **不是**，是同类隐患，单子点名要清 |

把第二件写成「修好了 flaky」就是把一次真实观测抹掉——所以分开记。
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WEB = REPO / "web"
CONFIG = WEB / "vitest.config.ts"
TESTS = WEB / "__tests__"
TICKET = REPO / "docs" / "blocked" / "UI07-LOCALE-TEST-IS-FLAKY.md"
TRACE = REPO / "docs" / "trace" / "FIX-04.md"
_STUB = re.compile(r"vi\.stubGlobal\(\s*[\"'](\w+)[\"']")


def _stubbing_files(root: Path) -> dict[str, set[str]]:
    """哪些文件 stub 了哪些全局。"""
    out: dict[str, set[str]] = {}
    for path in root.rglob("*.ts*"):
        names = set(_STUB.findall(path.read_text(encoding="utf-8")))
        if names:
            out[path.name] = names
    return out


def _restores_itself(path: Path) -> bool:
    return "unstubAllGlobals" in path.read_text(encoding="utf-8")


# ───────────────────────── acceptance②：隐患去掉了


def test_stubbed_globals_are_restored_after_every_test() -> None:
    """配置里 `unstubGlobals: true`。

    十个文件 stub 同一个 `fetch`，**没有一个自己还原**——
    一条用例设的 stub 会活到同文件后面的用例里，
    后者没设 stub 时拿到的是前者的答复，而它自己以为在用真的 fetch。
    """
    config = CONFIG.read_text(encoding="utf-8")

    assert re.search(r"unstubGlobals\s*:\s*true", config), (
        "配置没有还原被 stub 的全局")


def test_no_file_stubs_a_global_that_nobody_restores() -> None:
    """**覆盖判据**：每个 stub 全局的文件，要么自己还原，要么由配置兜底。

    只断言配置里那行在的话，哪天有人把配置改回去、而文件也没自己还原，
    这条照样绿。所以判的是**覆盖关系**。
    """
    config = CONFIG.read_text(encoding="utf-8")
    covered = bool(re.search(r"unstubGlobals\s*:\s*true", config))
    stubbing = _stubbing_files(TESTS)

    assert stubbing, "一个 stub 都没扫到：扫描面塌了，这条判据在空转"
    if covered:
        return
    uncovered = [name for name in stubbing
                 if not _restores_itself(TESTS / "app" / name)]
    assert uncovered == [], f"这些文件 stub 了全局却没人还原：{uncovered}"


def test_the_detector_sees_a_file_that_stubs_without_restoring() -> None:
    """**阴性对照**：造一个真 stub 却不还原的文件 → 必须被扫出来。

    没有这条，上面那个「都覆盖了」与「扫描面塌了」长得一模一样。
    """
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "leaky.test.tsx").write_text(
            'it("x", () => { vi.stubGlobal("fetch", vi.fn()); });\n',
            encoding="utf-8")
        (root / "clean.test.tsx").write_text(
            'it("y", () => { expect(1).toBe(1); });\n', encoding="utf-8")
        found = _stubbing_files(root)

    assert found == {"leaky.test.tsx": {"fetch"}}


# ───────────────────────── acceptance①：根因是实测出来的


def test_the_helper_waits_for_the_value_not_for_the_element() -> None:
    """根因那处：`renderLoadedPage` 等的是**值**，不是元素存在。

    屏上到位要两拍（数据 ready → 下拉出现；effect 冲刷 → 值对齐）。
    只等第一拍的话，断言值的那条用例在两拍之间抢跑——
    **实测 40 次循环里第 29 次抓到默认值 `zh`**。
    """
    source = (TESTS / "app" / "ui07.test.tsx").read_text(encoding="utf-8")
    helper = source[source.index("async function renderLoadedPage"):
                    source.index("describe(")]

    assert "waitFor" in helper
    assert ".value" in helper, "还是只等元素存在——那正是本卡修掉的东西"
    assert "expected.lang" in helper


def test_the_trace_records_both_runs_and_does_not_claim_a_proof_it_lacks() -> None:
    """trace 里要有**两次 10 连跑**的实测输出，且分得清哪件事是因。

    修完全绿 10 次**不等于**证明修对了（修之前也是 10 次全绿）。
    所以 trace 必须同时写下那 40 次循环的实测——那才是把因指出来的证据。
    """
    text = TRACE.read_text(encoding="utf-8")

    assert "754 passed" in text, "没有连跑输出"
    assert text.count("10 次") >= 2, "两次连跑没都记下来"
    assert "第 29 次" in text, "没有把复现那一次的实测写下来"


def test_the_ticket_is_closed() -> None:
    head = "\n".join(TICKET.read_text(encoding="utf-8").splitlines()[:16])

    assert "**状态** closed" in head
    assert "FIX-04" in head
