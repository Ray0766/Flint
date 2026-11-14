"""BL-09：V2 护栏尺子——数据模型已给 locale 的地方 NEVER 硬编码 zh/中文/weibo。

## 这把尺子挡的是什么

`docs/v2-backlog.md#V2-001`（owner @2026-07-30）的护栏原话：
「V1 写 prompt / 模板 / 相关性判断时，**在数据模型已给 locale 字段的地方
NEVER 硬编码「中文/zh/微博」假设**」。

一处硬编码今天是一行，V2 全球版时是一处要回头找的暗坑——
而它**不会报错**，只会在别的地区上悄悄给出中文口径的结果。

## 判据必须窄，否则没人再看它

三样**不算**违规，各有理由：

| 不算 | 理由 |
|---|---|
| 默认值（`locale: str = "zh-CN"`、`.get("locale", "zh-CN")`） | 默认说的是「今天跑哪个地区」，不是「只有这一个地区」 |
| 类型标注（`Literal["zh", "en"]`、`frozenset({"zh","en"})`） | 那是**声明支持面**，V2 时加一个成员即可 |
| 数据表的键（术语表的 `"zh"` 列） | 表是数据，不是分支 |

算违规的只有两类：**分支假设**（与地区字面量比较）与**调用点写死**
（给 `locale=` / `lang=` / `region=` 这类关键字实参传死值——调用方替用户
决定了地区，而那个值本该从 profile / 请求 / 配置里来）。

## 阴性对照是这把尺子的一半

「没有硬编码」与「尺子瞎了」在退出码上长得一模一样（都是 0）。
所以每一条「这样写不算违规」的旁边，都有一条「这样写必须红」。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from tools.check_locale_seam import (
    LOCALE_LITERALS,
    LOCALE_PARAMS,
    WHITELIST,
    audit,
    scan_source,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
# 一段**真违规**的源码，供尺子自证用（分支假设那一类）。
_VIOLATION_SOURCE = (
    "def f(lang: str) -> int:\n"
    '    return 1 if lang == "zh" else 2\n'
)


# ───────────────────────── 算违规的两类


def test_a_branch_on_a_hardcoded_locale_is_flagged() -> None:
    """acceptance①：`lang == "zh"` 这种分支假设即红。"""
    findings = scan_source('def f(lang):\n    return 1 if lang == "zh" else 2\n', "x.py")

    assert [f.kind for f in findings] == ["branch"]
    assert findings[0].line == 2


def test_membership_against_a_hardcoded_source_is_flagged() -> None:
    """`source_id in ("weibo", ...)` 同样是分支假设。"""
    findings = scan_source('def f(sid):\n    return sid in ("weibo", "gtrends")\n', "x.py")

    assert [f.kind for f in findings] == ["branch"]


def test_a_hardcoded_locale_argument_is_flagged() -> None:
    """acceptance①：`f(locale="zh-CN")` —— 调用方替用户定了地区。"""
    findings = scan_source('go(project, locale="zh-CN")\n', "x.py")

    assert [f.kind for f in findings] == ["hardcoded-arg"]
    assert "locale" in findings[0].detail


EXPECTED_PARAMS = ("lang", "locale", "region", "source_id")


def test_the_parameter_names_are_exactly_these_four() -> None:
    """判据面是闭集：加一个名字要在这里报到，删一个当场红。

    形参名**写死在这里**，不从 `LOCALE_PARAMS` 取：从被测常量取的话，
    「删掉一个名字」的变异体会连测试一起缩水，22 条全绿地活下来（变异考实测）。
    """
    assert tuple(sorted(LOCALE_PARAMS)) == EXPECTED_PARAMS


@pytest.mark.parametrize("param", EXPECTED_PARAMS)
def test_every_locale_shaped_parameter_is_covered(param: str) -> None:
    """四个形参名都在判据里——漏一个，那个名字下的写死就查不出来。"""
    findings = scan_source(f'go({param}="zh")\n', "x.py")

    assert [f.kind for f in findings] == ["hardcoded-arg"]


def test_the_finding_names_the_file_and_line() -> None:
    """acceptance①：命中要**点名文件行号**，否则报告没法用。"""
    findings = scan_source('\n\nif locale == "中文":\n    pass\n', "flint/a/b.py")

    assert (findings[0].path, findings[0].line) == ("flint/a/b.py", 3)


# ───────────────────────── acceptance③：正常用法不误伤


def test_a_default_value_is_not_a_violation() -> None:
    """默认值不算——默认说的是「今天跑哪个地区」。"""
    assert scan_source('def f(locale: str = "zh-CN") -> str:\n    return locale\n', "x.py") == []


def test_a_get_with_a_fallback_is_not_a_violation() -> None:
    """`payload.get("locale", "zh-CN")` 不算：那是取值带兜底，不是分支。"""
    assert scan_source('locale = payload.get("locale", "zh-CN")\n', "x.py") == []


def test_a_type_annotation_is_not_a_violation() -> None:
    """`Literal["zh", "en"]` 是**声明支持面**，V2 加一个成员即可。"""
    assert scan_source('from typing import Literal\nLang = Literal["zh", "en"]\n', "x.py") == []


def test_a_declared_support_set_is_not_a_violation() -> None:
    """`frozenset({"zh", "en"})` 同理（`flint/profile/prefs.py` 的真实写法）。"""
    assert scan_source('_LANGS = frozenset({"zh", "en"})\n', "x.py") == []


def test_a_data_table_key_is_not_a_violation() -> None:
    """术语表里的 `"zh"` 列是数据，不是分支（`flint/norm/terms.py` 的真实写法）。"""
    assert scan_source('zh = entry["zh"]\nTABLE = {"zh": 1, "en": 2}\n', "x.py") == []


def test_a_correct_locale_dispatch_passes() -> None:
    """acceptance③ 正例：**按 locale 分派**的正确写法必须放行。

    这段代码把 locale 当参数用（查表 + 透传），一处都没写死——
    误伤它的尺子会逼着人把正确写法改成别的样子。
    """
    correct = (
        "RULES = {}\n"
        "def judge(text: str, locale: str) -> float:\n"
        "    rules = RULES.get(locale) or RULES[DEFAULT_LOCALE]\n"
        "    return rules.score(text, locale=locale)\n"
    )

    assert scan_source(correct, "x.py") == []


def test_comments_and_docstrings_are_not_code() -> None:
    """注释与 docstring 里提 zh/微博是正当的（多半是在说明为什么不能写死）。"""
    source = (
        '"""这里说明为什么 NEVER 写死 zh / 中文 / weibo。"""\n'
        '# lang == "zh" 这种写法就是本尺子要挡的\n'
        "def f(lang: str) -> str:\n"
        "    return lang\n"
    )

    assert scan_source(source, "x.py") == []


# ───────────────────────── acceptance④：白名单逐条列名


def test_the_whitelist_names_files_one_by_one_with_a_reason() -> None:
    """豁免**逐条列名 + 写明理由**，NEVER 整目录放行。

    放一个目录，下一个人会把新代码写进那个目录。
    """
    assert WHITELIST, "白名单为空说明豁免机制没建"
    for path, reason in WHITELIST.items():
        assert path.endswith(".py"), f"白名单里出现了目录：{path}"
        assert (REPO_ROOT / path).exists(), f"白名单条目已不在盘上：{path}"
        assert len(reason) >= 10, f"{path} 的豁免理由太短：{reason}"


def test_whitelisted_hits_are_reported_separately_not_hidden() -> None:
    """白名单里的命中**照样列出来**（在 `exempted` 里），只是不判红。

    藏起来的话，「白名单里那些文件有多少地区假设」这件事就没人知道了。

    这一条是变异考补上来的：首版只断言 `exempted` 这个键在报告里，
    于是「豁免 = 直接丢弃」的变异体 22 条全绿地活了下来——因为
    `flint/sources/weibo.py` **今天一处命中都没有**，`exempted` 本来就是空的。
    改成注入一份自造白名单，让豁免机制自己走一遍。
    """
    probe = REPO_ROOT / "tools" / "_bl09_exempt_probe.py"
    probe.write_text(_VIOLATION_SOURCE, encoding="utf-8")
    try:
        without = audit(["tools"], whitelist={})
        with_rule = audit(["tools"], whitelist={"tools/_bl09_exempt_probe.py": "自造探针"})
    finally:
        probe.unlink()

    assert any("_bl09_exempt_probe" in f["path"] for f in without["findings"])
    # **只看探针那一条**。`GAUGE-07` 把尺子加宽到九区之后，
    # `tools/` 下还有另一处真命中（`orthogonality_check.py` 的自证反例，
    # 它在真白名单里）——这里传的是**自造白名单**，所以它会照常出现在
    # `findings` 里。判「findings 全空」会把那处无关命中算成本条的失败。
    assert not [f for f in with_rule["findings"]
                if "_bl09_exempt_probe" in f["path"]], "白名单没起作用"
    assert any("_bl09_exempt_probe" in f["path"] for f in with_rule["exempted"]),         "豁免的命中被丢掉了，而不是列进 exempted"


def test_the_real_whitelist_exempts_nothing_today() -> None:
    """现状登记：`flint/sources/weibo.py` 今天**一处命中都没有**。

    白名单条目是**预留**的（acceptance④ 要求机制存在且只留给中国特有的源），
    不是在掩盖什么。哪天 weibo 源真写了地区分支，它会进 `exempted` 而不是判红——
    而这一条会红，提醒那时的人来更新这句话。
    """
    report = audit(["flint"])

    assert report["exempted"] == []


# ───────────────────────── acceptance②：对当前仓库真跑


def test_the_repository_is_clean_today() -> None:
    """全仓实跑（真实结果写进 `docs/trace/BL-09.md#4`）。

    今天是干净的——这把尺子的价值在于**挡住明天**：
    现在挡比 V2 时回头找便宜。
    """
    report = audit(["flint", "eval", "harness", "tools"])

    assert report["unreadable"] == [], "有文件读不了，扫描面是残的"
    assert report["findings"] == [], f"硬编码的地区假设：{report['findings']}"
    assert report["scanned"] > 200, "扫描面太小，可能根本没扫到 flint/"


def test_the_cli_exits_zero_on_a_clean_tree() -> None:
    """命令行形态也跑一遍（它才是接进门的那个）。"""
    done = subprocess.run(
        [sys.executable, "tools/check_locale_seam.py"],
        cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8",
        errors="replace", check=False,
    )

    assert done.returncode == 0, done.stdout + done.stderr


def test_the_cli_exits_one_when_a_violation_exists(tmp_path: Path) -> None:
    """阴性对照：造一处真违规 → 退出码 1 且点名。

    没有这一条，「今天全仓干净」与「尺子瞎了」长得一模一样。
    """
    offender = REPO_ROOT / "tools" / "_bl09_violation_probe.py"
    offender.write_text('def f(lang: str) -> int:\n    return 1 if lang == "zh" else 2\n',
                        encoding="utf-8")
    try:
        done = subprocess.run(
            [sys.executable, "tools/check_locale_seam.py", "--root", "tools"],
            cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8",
            errors="replace", check=False,
        )
    finally:
        offender.unlink()

    assert done.returncode == 1
    assert "_bl09_violation_probe.py:2" in done.stderr


def test_a_broken_file_is_reported_not_counted_as_clean(tmp_path: Path) -> None:
    """读不了的文件要**报出来**，NEVER 当成「没命中」。

    当成没命中的话，一个语法坏掉的文件会让报告说「全仓干净」。
    """
    broken = REPO_ROOT / "tools" / "_bl09_broken_probe.py"
    broken.write_text("def f(:\n", encoding="utf-8")
    try:
        report = audit(["tools"])
    finally:
        broken.unlink()

    assert any("_bl09_broken_probe" in item for item in report["unreadable"])


def test_the_literals_cover_the_three_names_the_guardrail_names() -> None:
    """护栏原话点名的三样都在字面量集合里：中文 / zh / 微博。"""
    assert {"zh", "中文", "微博", "weibo"} <= LOCALE_LITERALS
