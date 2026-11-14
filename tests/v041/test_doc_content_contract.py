"""DOC-01：`Doc` 增正文三件套（owner 2026-08-04 裁决：方案 A）。

## 这张卡在补什么

此前 `Doc` 只有 `title` + `url`。证据卡因此只能引到**标题与链接**——
引不到正文里的任何一句话。「证据」这个词在产品里说的是「可核验的出处」，
而一个标题核验不了什么。

## 走 additive 通道，`contracts/` 一字不动（acceptance②）

冻结件是唯一真相（CLAUDE.md S2-1）。改它要走 PDD 修订通道，那是 owner 的事。
本卡改的是 **v04 工作副本** `contracts_v04/models_v04.py`，由
`tools/check_frozen_additive.py` 逐字段核对「只加不删」。
判据两件事都查：新字段在副本里、且本体没被碰过。

## 四个字段，各有各的不肯含糊

| 字段 | 为什么不能省 |
|---|---|
| `content` | `None` = **还没提取**，不是「这篇没有正文」。两者分不开，重跑提取时就不知道该跳过谁 |
| `content_sha256` | 算的是**原文**（截断前）。截断后再算，验证与去重两件事同时失灵 |
| `content_truncated` | 截断 MUST 如实标记——下游据此知道自己拿到的不是全文 |
| `source_file_ref` | PDF 一类原件的位置。**正文进库、原件进文件**，两条路各归各的 |
"""
from __future__ import annotations

import ast
import subprocess
import sys
from dataclasses import fields
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FROZEN = REPO / "contracts" / "models.py"
V04 = REPO / "contracts_v04" / "models_v04.py"
CHECKER = REPO / "tools" / "check_frozen_additive.py"

# 卡上逐字写死的三个字段 + PDF 原件那一位。标注也逐字比——
# `str | None` 与 `str` 是两件事：后者逼着每个构造点现在就给一个值。
REQUIRED: dict[str, str] = {
    "content": "str | None",
    "content_sha256": "str | None",
    "content_truncated": "bool",
    "source_file_ref": "str | None",
}

CAP_BYTES = 2 * 1024 * 1024


def _doc_class(path: Path) -> ast.ClassDef:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "Doc":
            return node
    raise AssertionError(f"{path.name} 里没有 Doc 类")


def _annotations(node: ast.ClassDef) -> dict[str, str]:
    return {
        stmt.target.id: ast.unparse(stmt.annotation)
        for stmt in node.body
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)
    }


def _module_text() -> str:
    return V04.read_text(encoding="utf-8")


# ───────────────────────── 一、四个字段在，标注逐字对（acceptance①④）


def test_the_working_copy_declares_all_four_fields() -> None:
    got = _annotations(_doc_class(V04))

    missing = [name for name in REQUIRED if name not in got]
    assert missing == [], f"工作副本的 Doc 缺这些字段：{missing}"


def test_each_annotation_is_the_one_the_card_wrote() -> None:
    """标注逐字比：`str | None` 与 `str` 是两件事。

    写成 `str` 的话，「还没提取」就无处表达——每个构造点被逼着现在给一个值，
    而它们手上没有正文，只能给空串。空串与「这篇文章正文是空的」从此分不开。
    """
    got = _annotations(_doc_class(V04))

    for name, annotation in REQUIRED.items():
        assert got[name] == annotation, f"{name} 的标注是 {got[name]}，卡上写的是 {annotation}"


def test_all_four_carry_defaults_so_existing_call_sites_keep_working() -> None:
    """四个都要有默认值：增量 NEVER 破坏既有构造点。"""
    node = _doc_class(V04)
    defaults = {
        stmt.target.id: stmt.value
        for stmt in node.body
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)
    }

    for name in REQUIRED:
        assert defaults[name] is not None, f"{name} 没有默认值，既有构造点会全部报错"
    assert ast.unparse(defaults["content_truncated"]) == "False"
    for name in ("content", "content_sha256", "source_file_ref"):
        assert ast.unparse(defaults[name]) == "None"


def test_the_dataclass_really_constructs_without_the_new_fields() -> None:
    """把断言压到**真构造**上：AST 说有默认值，与「真的能不传就构造出来」是两件事。"""
    sys.path.insert(0, str(REPO))
    from contracts_v04.models_v04 import Doc

    doc = Doc(
        doc_id="d-1", source_id="s-1", kind="webpage", title="t", url="https://x.test",
        published_at=None, meta={}, origin="retrieved", access="public", region=None,
        source_country=None,
    )

    assert doc.content is None
    assert doc.content_sha256 is None
    assert doc.content_truncated is False
    assert doc.source_file_ref is None
    assert {f.name for f in fields(Doc)} >= set(REQUIRED)


# ───────────────────────── 二、走 additive 通道，本体一字不动（acceptance②）


def test_the_frozen_original_never_grew_these_fields() -> None:
    """`contracts/` 本体在本卡内一字不动——它归 PDD 修订通道，不归执行侧。"""
    frozen = _annotations(_doc_class(FROZEN))

    for name in REQUIRED:
        assert name not in frozen, f"冻结件本体被改了：{name} 出现在 contracts/models.py"


def test_the_additive_checker_passes_on_both_pairs() -> None:
    """双通过：models 与 protocols 两对都过 `check_frozen_additive.py`。

    只跑 models 那一对的话，protocols 副本被改坏时这条判据看不见——
    而卡上写的是「双通过」。
    """
    for base, copy in (
        ("contracts/models.py", "contracts_v04/models_v04.py"),
        ("contracts/protocols.py", "contracts_v04/protocols_v04.py"),
    ):
        done = subprocess.run(
            [sys.executable, str(CHECKER), base, copy],
            cwd=REPO, capture_output=True, text=True, encoding="utf-8", check=False)
        assert done.returncode == 0, f"{copy} 没过 additive：{done.stdout}{done.stderr}"


def test_the_new_fields_come_after_the_frozen_ones() -> None:
    """新字段排在冻结件那批之后。

    dataclass 的字段顺序是**位置参数的顺序**：插在中间的话，
    所有按位置构造 `Doc(...)` 的地方会静默地把值装错位——那种错不报，只是数据错了。
    """
    order = [name for name in _annotations(_doc_class(V04))]
    frozen_order = [name for name in _annotations(_doc_class(FROZEN))]

    assert order[: len(frozen_order)] == frozen_order, "冻结件那批字段的顺序被动过了"
    for name in REQUIRED:
        assert order.index(name) >= len(frozen_order), f"{name} 插进了冻结件那批中间"


# ───────────────────────── 三、语义写进 docstring（acceptance③）


def test_the_cap_is_a_named_constant_not_a_scattered_literal() -> None:
    """2 MB 上限只有一处真相。

    散成字面量的话，改上限要靠全仓搜一个数字——漏掉的那处会在某条路径上
    按旧上限截断，而它截出来的东西照样标着「未截断」。
    """
    text = _module_text()

    assert "DOC_CONTENT_MAX_BYTES = 2 * 1024 * 1024" in text, "上限不是一个具名常量"
    sys.path.insert(0, str(REPO))
    from contracts_v04.models_v04 import DOC_CONTENT_MAX_BYTES

    assert DOC_CONTENT_MAX_BYTES == CAP_BYTES


def _doc_field_comments() -> str:
    """`Doc` 类里那段字段说明（从本卡的增量标记到类结束）。

    判在这一段上，不判整份文件：整份文件里「截断」「哈希」这些词到处都是，
    按全文判的话，把这一段整条删掉毫无反应。
    """
    text = _module_text()
    start = text.find("# —— v0.4.1 纯新增 · DOC-01")
    assert start != -1, "找不到本卡那段字段说明"
    end = text.find("\n\n@dataclass", start)
    assert end != -1
    return text[start:end]


def test_the_field_notes_say_what_none_means_for_content() -> None:
    """`None` = **还没提取**，不是「这篇没有正文」——两者要分得开。"""
    notes = _doc_field_comments()

    assert "还没提取" in notes
    assert "不是「这篇没有正文」" in notes


def test_the_field_notes_say_the_hash_is_of_the_original() -> None:
    """哈希算的是**截断前**那一份：截断后再算，验证与去重同时失灵。"""
    notes = _doc_field_comments()

    assert "截断前" in notes, "没写清哈希算的是原文"
    assert "去重" in notes and "验证" in notes, "没写清哈希的两个用途"


def test_the_field_notes_state_the_cap_and_that_truncation_must_be_marked() -> None:
    notes = _doc_field_comments()

    assert "DOC_CONTENT_MAX_BYTES" in notes, "字段说明没指向那个上限常量"
    assert "2 MB" in notes
    assert "如实标记" in notes, "没写「截断 MUST 如实标记」"


def test_the_field_notes_keep_the_body_and_the_original_file_on_separate_paths() -> None:
    """acceptance④：**正文进库、原件进文件**，两条路各归各的。"""
    notes = _doc_field_comments()

    assert "正文进库" in notes and "原件进文件" in notes
    assert "PDF" in notes, "没点名 PDF 这一类原件"


def test_the_ruling_is_attributed() -> None:
    """裁决要写明是谁、哪天、哪个方案——不写的话，下一个人只看到「字段多了三个」。"""
    notes = _doc_field_comments()

    assert "owner 2026-08-04" in notes
    assert "方案 A" in notes
