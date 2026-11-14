"""GAUGE-10 · 第二份扫描器同样不剥注释——注释里写路径会被当成真调用。

## 「只在字符串里找」不等于「排除了注释」

两把尺子的说明都写着这句话，而它**对反引号引的路径不成立**：

```ts
// `/projects/{}/proposal` 与 `/projects/{}/report` 此前藏在
// `/projects/{}/{}` 那条「扫不动」里
```

`//` 后面那对反引号 **本身就长得像模板串**。于是一句解释性的注释被读成三次真调用。

`TYPE-04` 被这件事绊了两次，修了 `tools/check_fe_be_parity.py` 那一半，
另一半（`tools/check_fe_api_contract.py`）**只能绕行**：把注释改成不带反引号的写法。

**绕行不是修好**：下一个人写注释时还会踩，而他踩到的表现是「全局门红」——
一句诚实的说明性注释让门红，人学到的是「别写注释」。

## 剥注释要**保住行号**

第二份扫描器报的是 `file:line`。整段删掉注释会让后面每一行的行号左移，
于是尺子报的位置指向别处——**一个指错地方的红比不报更糟**。

所以这里用的是「把注释字符换成等长空白」：偏移量逐字节不变，行号自然对。

## 实测（改前）

```
line   5  GET   /account                  ← 唯一的真调用
line   1  GET   /projects/{}/proposal     ← 注释
line   1  GET   /projects/{}/report       ← 注释
line   2  GET   /projects/{}/{}           ← 注释
line   3  GET   /billing                  ← 块注释
```
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tools.check_fe_api_contract import frontend_calls
from tools.check_fe_be_parity import frontend_calls as parity_calls

# 一句解释性注释（含反引号路径）+ 一处**真**调用。
# 两者必须被区分开——这就是本卡的全部内容。
SOURCE = """// 说明：`/projects/{}/proposal` 与 `/projects/{}/report` 此前藏在
// `/projects/{}/{}` 那条「扫不动」里。
/* 块注释里也写一条：`/billing` */
export async function real(base: string) {
  return fetch(`${base}/account`, { method: "GET" });
}
"""
COMMENTED = ("/projects/{}/proposal", "/projects/{}/report",
             "/projects/{}/{}", "/billing")


def _write(tmp: Path, text: str = SOURCE) -> Path:
    """建一份 `web/lib/x.ts`，返回**那个 web 目录**。

    两把尺子收的目录不是一层：`check_fe_api_contract.frontend_calls` 收被扫目录
    本身，`check_fe_be_parity.frontend_calls` 收 `web` 并自己拼 `lib`。
    这里统一返回 web，各自在调用点取自己那一层——**NEVER 把这层差别藏进辅助函数**，
    藏起来的话下一个人会以为两把尺子看的是同一批文件。
    """
    lib = tmp / "lib"
    lib.mkdir(parents=True, exist_ok=True)
    (lib / "x.ts").write_text(text, encoding="utf-8")
    return tmp


# ───────────────────────── acceptance①③：两把尺子都不再把注释当调用


def test_the_contract_scanner_no_longer_reads_a_comment_as_a_call(
    tmp_path: Path,
) -> None:
    """`check_fe_api_contract`：注释里那四条一条都不许出现。"""
    paths = {call["path"] for call in frontend_calls(_write(tmp_path) / "lib")}

    assert paths & set(COMMENTED) == set(), (
        f"注释里的路径被当成了真调用：{sorted(paths & set(COMMENTED))}")


def test_the_parity_scanner_no_longer_reads_a_comment_as_a_call(
    tmp_path: Path,
) -> None:
    """`check_fe_be_parity`（第 3 批修的那一半）：**同一份输入**再验一次。

    两把尺子分别修、分别验——只验一把的话，另一把哪天退回去没人知道。
    """
    # GAUGE-14：把注释里那四条**也放进路由表**——它们全是真路由的形状，
    # 交集滤不掉它们。滤掉它们的必须是「剥注释」那一步，
    # 而这条判据要的正是那一步还在。
    paths = parity_calls(_write(tmp_path), set(COMMENTED) | {"/account"})

    assert paths & set(COMMENTED) == set(), (
        f"注释里的路径被当成了真调用：{sorted(paths & set(COMMENTED))}")


def test_the_real_call_is_still_found_by_both(tmp_path: Path) -> None:
    """**阴性对照**：真调用仍被两把尺子抓到。

    剥注释剥过了头（比如把整个文件当注释）时，上面两条照样绿——
    那时尺子什么都不报，而「什么都没报」与「没有问题」长得一模一样。
    """
    web = _write(tmp_path)

    assert "/account" in {call["path"] for call in frontend_calls(web / "lib")}
    assert "/account" in parity_calls(web, set(COMMENTED) | {"/account"})


# ───────────────────────── 行号要保住


def test_stripping_comments_keeps_the_line_numbers_honest(tmp_path: Path) -> None:
    """真调用报的行号仍是它在**原文件**里的那一行。

    整段删掉注释会让后面每一行左移——尺子于是指向别处，
    而**一个指错地方的红比不报更糟**：人会去改一段本来对的代码。
    """
    calls = [c for c in frontend_calls(_write(tmp_path) / "lib")
             if c["path"] == "/account"]

    assert calls, "真调用没扫到"
    assert calls[0]["line"] == 5, f"行号左移了：报 {calls[0]['line']}，实际第 5 行"


def test_the_stripper_replaces_comments_with_blanks_not_nothing() -> None:
    """剥注释的那一步**逐字节保长**：偏移量不变，行号才不会漂。"""
    from tools.check_fe_api_contract import _blank_comments

    text = "a\n// `/billing`\nb\n/* `/x` */\nc\n"
    blanked = _blank_comments(text)

    assert len(blanked) == len(text), "长度变了：偏移量会漂"
    assert blanked.count("\n") == text.count("\n"), "行数变了：行号会漂"
    assert "/billing" not in blanked and "/x" not in blanked
    assert blanked.startswith("a\n") and blanked.rstrip().endswith("c")


# ───────────────────────── acceptance②：根因写进判据


def test_both_scanners_stopped_claiming_that_strings_exclude_comments() -> None:
    """那句「只在字符串里找就等于排除了注释」**不许再出现在说明里**。

    文档与行为不一致时，下一个人会照文档去查，然后查错地方——
    这正是本单绊了两次的原因。
    """
    for tool in ("check_fe_api_contract.py", "check_fe_be_parity.py"):
        text = (REPO / "tools" / tool).read_text(encoding="utf-8")
        assert "注释" in text, f"{tool} 没提注释这件事"
        # 两份都要写明反引号那条：光说「剥了注释」，下一个人不知道**为什么**要剥。
        assert "反引号" in text, f"{tool} 没写清根因（反引号本身长得像模板串）"


def test_the_crlf_sibling_ticket_is_still_referenced() -> None:
    """兄弟单 `CRLF-BREAKS-COMMENT-STRIPPING` 仍挂着。

    那张单说的是 JS 侧尺子按 `\\n` 剥注释、遇 CRLF 失效；本卡是 Python 侧
    **根本没剥**。两处是同一件事的两半，**NEVER 修了一半就当整件事完了**。
    """
    ticket = REPO / "docs" / "blocked" / "CRLF-BREAKS-COMMENT-STRIPPING.md"

    assert ticket.exists(), "兄弟单不见了"


# ───────────────────────── acceptance④：单子关掉


def test_the_ticket_is_closed() -> None:
    ticket = REPO / "docs" / "blocked" / "SCANNERS-DO-NOT-STRIP-COMMENTS.md"
    head = "\n".join(ticket.read_text(encoding="utf-8").splitlines()[:16])

    assert "**状态** closed" in head
    assert "GAUGE-10" in head

def test_a_multi_line_block_comment_does_not_shift_the_line_numbers(
    tmp_path: Path,
) -> None:
    """**跨行块注释**里的换行要原样留着。

    变异考逼出来的：把块注释整段换成空格（换行也吃掉）时，上面那条行号判据
    照样绿——因为它用的块注释只有一行，吃不吃换行都不影响。
    多行块注释才量得到：吃掉两个换行，后面每一行的行号都往上跳两行。
    """
    text = (
        "/*\n"
        " * 三行的块注释\n"
        " */\n"
        "export async function ok(base: string) {\n"
        '  return fetch(`${base}/account`);\n'
        "}\n"
    )
    calls = [c for c in frontend_calls(_write(tmp_path, text) / "lib")
             if c["path"] == "/account"]

    assert calls, "真调用没扫到"
    assert calls[0]["line"] == 5, (
        f"行号漂了：报 {calls[0]['line']}，实际第 5 行——块注释的换行被吃掉了")


def test_a_url_inside_a_string_is_not_mistaken_for_a_comment(
    tmp_path: Path,
) -> None:
    """字符串里的 `//`（比如 `"http://x"`）**NEVER 当成注释起点**。

    也是变异考逼出来的：拿掉剥注释那段的引号状态机之后，原有判据全绿——
    因为没有一条判据里出现过带 `//` 的字符串。

    这里把那个字符串放在**同一行的真调用之前**：不认引号的话，
    从 `//` 起到行尾全被抹白，那次真调用连同它一起消失——
    尺子于是报「前端没调这条」，而前端明明在调。
    """
    text = (
        "export function build(base: string) {\n"
        '  return { ref: "http://example.invalid/x", url: `${base}/account` };\n'
        "}\n"
    )
    paths = {c["path"] for c in frontend_calls(_write(tmp_path, text) / "lib")}

    assert "/account" in paths, (
        "真调用被吞了：字符串里的 // 被当成了注释起点")
