"""GAUGE-07 · locale 全仓尺加宽到九区代码。

## 此前这把尺子只守住了一条轴

`PRINCIPLES#A3` 明写是**两条轴**：语言与地区。
而 `LOCALE_LITERALS` 里**九区代码一个都没有**，于是这两种写法从它下面走得过去：

```python
if region == "CN":            # 分支假设
select_sources(region="CN")   # 调用点写死
```

`BE-07` 的变异考⑳ 就是这么过的——**两种都漏了**。

这把尺子自己的 docstring 写着：「一处硬编码今天是一行，V2 全球版时是一处
要回头找的暗坑——**而它不会报错**」。地区那一半此前就在这个状态。

## 九区**取自冻结件**，不手抄

手抄的清单不会跟着冻结件变：V2 加一个地区，尺子仍按九个量，
而**新加的那个地区从此不在护栏内**——最需要护栏的恰恰是新地区。

## 加宽后全仓只红 2 处，且都在同一个文件

实测（先量再定豁免，卡面 acceptance③ 的顺序）：

```
findings: 2   全部 kind=branch   全部在 tools/orthogonality_check.py
```

那两处是**另一把尺子的自证反例**（`_BROKEN` 里故意写坏的 A3 接线）。
判它红等于逼那把尺子删掉自己的反例——而那条反例守的正是本尺子同一条纪律。
所以豁免**逐条列名**到文件级，NEVER 用通配一刀切。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import get_args

from contracts_v04.models_v04 import Region
from tools.check_locale_seam import (
    LOCALE_LITERALS,
    WHITELIST,
    audit,
    scan_source,
)

REPO = Path(__file__).resolve().parents[2]
RULER = REPO / "tools" / "check_locale_seam.py"
TICKET = REPO / "docs" / "blocked" / "LOCALE-SEAM-RULER-MISSES-REGION-CODES.md"


# ───────────────────────── acceptance①：地区清单并入，且取自冻结件


def test_all_regions_are_in_the_literal_set() -> None:
    """护栏 MUST 盖住**冻结件里的每一个**地区码。

    数目写死在这里的话，`DEC-056` 加 HK 那天这条判据会红在「数不对」上，
    而它真正要守的是「一个都没漏出护栏」——所以这里比的是**集合包含**，
    数目只作为「清单真的读到了」的下界。
    """
    frozen = set(get_args(Region))

    assert len(frozen) >= 9, f"只读到 {len(frozen)} 个地区，清单没读全"
    assert frozen <= set(LOCALE_LITERALS), (
        f"这些地区不在护栏内：{sorted(frozen - set(LOCALE_LITERALS))}"
    )


def test_the_regions_come_from_the_contract_not_a_hand_copied_list() -> None:
    """**判源码**：那九个代码不许以字面量清单的形式写在尺子里。

    手抄的清单不会跟着冻结件变。V2 加一个地区，尺子仍按九个量，
    而新加的那个地区从此不在护栏内——**最需要护栏的恰恰是新地区**。
    """
    source = RULER.read_text(encoding="utf-8")

    assert "_frozen_regions" in source
    assert "contracts_v04.models_v04 import Region" in source
    # 九个代码里，除了注释与豁免理由，NEVER 在集合字面量里出现。
    literal_block = source.split("LOCALE_LITERALS: Final[frozenset[str]] = frozenset(")[1]
    literal_block = literal_block.split(")")[0]
    for code in get_args(Region):
        assert f'"{code}"' not in literal_block, (
            f"{code} 被手抄进了字面量集合——它该从冻结件来"
        )


def test_an_empty_contract_is_loud_not_silently_empty() -> None:
    """取不到就 raise，**NEVER 退化成空集合**。

    空集合会让这半条护栏静静地不再报任何东西，
    而报告上写的是「0 处违规」——那两句话在退出码上一模一样。
    """
    source = RULER.read_text(encoding="utf-8")
    body = source.split("def _frozen_regions()")[1].split("\ndef ")[0]

    assert "raise RuntimeError" in body
    assert "return frozenset()" not in body


def test_the_language_axis_did_not_regress() -> None:
    """加宽地区那一半时，语言那一半原样保留。"""
    assert {"zh", "zh-CN", "zh_CN", "zh-Hans", "中文"} <= set(LOCALE_LITERALS)
    # `en` **仍然不在**：护栏挡的是「中文假设」，
    # 把 en 算进来会把「支持面声明」误报成假设。
    assert "en" not in LOCALE_LITERALS


# ───────────────────────── acceptance④：两种写法都要报红


def test_a_branch_that_assumes_a_region_is_reported() -> None:
    """**阴性对照一**：`if region == "CN":` 这种分支假设。

    `BE-07` 的变异考⑳ 当时漏的就是它。
    """
    findings = scan_source(
        'def pick(region: str) -> str:\n'
        '    if region == "CN":\n'
        '        return "weibo"\n'
        '    return "gtrends"\n',
        "probe.py")

    assert [f for f in findings if f.kind == "branch"], "分支假设没被报出来"
    assert "CN" in findings[0].detail


def test_a_call_site_that_hardcodes_a_region_is_reported() -> None:
    """**阴性对照二**：`select_sources(region="CN")` 这种调用点实参。

    与上一条是**两种不同的写法**——`BE-07` 那次两种都漏了，
    所以这里各判一条，NEVER 合成一条。
    """
    findings = scan_source(
        'def go() -> None:\n    select_sources(region="CN")\n', "probe.py")

    hardcoded = [f for f in findings if f.kind == "hardcoded-arg"]
    assert hardcoded, "调用点写死没被报出来"
    assert "region" in hardcoded[0].detail and "CN" in hardcoded[0].detail


def test_every_one_of_the_nine_regions_is_caught_not_just_cn() -> None:
    """九个**逐个**验，NEVER 只验 CN。

    只验一个的话，「集合里少了 SG」这种缺口照样绿。
    """
    missed = []
    for code in get_args(Region):
        found = scan_source(
            f'def pick(region: str) -> str:\n'
            f'    if region == "{code}":\n'
            f'        return "x"\n'
            f'    return "y"\n',
            "probe.py")
        if not found:
            missed.append(code)

    assert missed == [], f"这些地区写死了却不报：{missed}"


def test_a_type_declaration_is_not_a_violation() -> None:
    """**豁免类一**：类型标注是**声明支持面**，不是假设。

    `Literal["zh", "en"]` / `frozenset({...})` 说的是「支持这些」，
    V2 时加一个成员即可——判它红会逼人把支持面藏起来。
    """
    findings = scan_source(
        'from typing import Literal\n'
        'Region = Literal["CN", "US", "JP"]\n'
        'SUPPORTED = frozenset({"CN", "US"})\n',
        "probe.py")

    assert findings == [], f"类型声明被误报：{findings}"


def test_a_data_table_key_is_not_a_violation() -> None:
    """**豁免类二**：数据表的键。

    术语表里的 `"zh"` 列、按地区分组的字典键——那是数据，不是分支假设。
    """
    findings = scan_source(
        'TERMS = {"CN": "中国", "US": "美国", "JP": "日本"}\n'
        'DEFAULT_REGION = "CN"\n',
        "probe.py")

    assert findings == [], f"数据表的键被误报：{findings}"


# ───────────────────────── acceptance②③：豁免写实、先量再定


def test_the_repository_is_clean_after_the_widening() -> None:
    """加宽之后全仓干净——白名单外零命中。"""
    report = audit(["flint", "eval", "harness", "tools"])

    assert report["findings"] == [], report["findings"][:4]


def test_the_only_whitelisted_hits_are_the_ones_we_measured() -> None:
    """**判等值**：白名单内的命中逐条对上实测。

    加宽时先跑了一遍全仓（卡面 acceptance③ 的顺序：先量再定豁免），
    结果是 **2 处、全在 `tools/orthogonality_check.py`**。
    多一处要有人确认，少一处说明那把尺子的反例被删了。
    """
    report = audit(["flint", "eval", "harness", "tools"])

    # `exempted` 在 `--json` 下是计数、在库调用下是明细列表——两种都认，
    # 判的是**条数**（这才是「实测 2 处」那件事本身）。
    exempted = report["exempted"]
    count = exempted if isinstance(exempted, int) else len(exempted)

    assert count == 2, (
        f"白名单内命中 {count} 处，实测是 2——"
        f"多一处要有人确认，少一处说明那把尺子的反例被删了"
    )
    if not isinstance(exempted, int):
        # 有明细时连**在哪个文件**也判上：换个文件命中同样要有人来确认。
        assert {row["path"] for row in exempted} == {
            "tools/orthogonality_check.py"}
    # 扫描面也要判：扫到的文件数塌了，上面那个 0 就毫无意义。
    assert report["scanned"] > 300, f"只扫到 {report['scanned']} 个文件：扫描面塌了"
    unreadable = report["unreadable"]
    assert (unreadable if isinstance(unreadable, int) else len(unreadable)) == 0, (
        f"有文件读不了，那部分等于没量：{unreadable}"
    )


def test_every_whitelist_entry_names_a_file_and_gives_a_reason() -> None:
    """豁免**逐条列名 + 写明理由**，NEVER 通配一刀切。

    放一个目录，下一个人会把新代码写进那个目录——
    这句话是这把尺子自己的 docstring 写的。
    """
    for path, why in WHITELIST.items():
        assert path.endswith(".py"), f"{path} 不是一个文件——不许放目录"
        assert "*" not in path and "?" not in path, f"{path} 用了通配"
        assert len(why) > 20, f"{path} 的豁免理由太短：{why!r}"
        assert (REPO / path).exists(), f"豁免了一个不存在的文件：{path}"


def test_the_new_whitelist_entry_explains_it_is_another_rulers_control() -> None:
    """新加的那条要说清**它是另一把尺子的自证反例**。

    判它红等于逼那把尺子删掉自己的反例——而那条反例守的正是同一条纪律。
    """
    why = WHITELIST["tools/orthogonality_check.py"]

    assert "反例" in why
    assert "_BROKEN" in why


def test_the_ruler_still_runs_from_the_command_line() -> None:
    """CLI 跑法也要能跑——`python tools/…` 时仓库根不在 `sys.path`。

    少了那句 `sys.path.insert`，这半条护栏会崩在**读冻结件**这一步，
    看起来像「冻结件坏了」。（`WIRE-01` 在另一把尺子上撞过同一个坑。）
    """
    done = subprocess.run(
        [sys.executable, str(RULER)], cwd=REPO,
        capture_output=True, text=True, encoding="utf-8", check=False)

    assert done.returncode == 0, done.stdout[-500:] + done.stderr[-500:]
    assert "没有硬编码的地区假设" in done.stdout
    # 白名单内的命中要**显示出来**，不是悄悄吞掉。
    assert "白名单内命中 2 处" in done.stdout


def test_the_ticket_is_closed() -> None:
    head = "\n".join(TICKET.read_text(encoding="utf-8").splitlines()[:16])

    assert "已关闭" in head
    assert "GAUGE-07" in head
