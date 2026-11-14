"""FIX-17：两条来源的说法并排，**屏上要看得出谁说的**。

## 改前

`SourceColumns` 把来源只放进 `data-source-id`，渲染逐字是：

```tsx
<li data-source-id={s.sourceId}>
  <span data-testid="source-statement-text">{s.text}</span>
</li>
```

**DOM 里有、屏上一个字都没有。** 而这个组件的全部理由写在它自己的文件头：

> 读者失去了「谁说的」这个唯一能判断可信度的东西。

改前的它，说的正是自己。

## 为什么地区那一列不够顶

列标题是地区（`CN` / `未归区`），只在两个源恰好分属两个区时才顺带区分了它们。
库里的实况是 `global = 103 · CN = 89 · NULL = 1`——绝大多数簇的源要么同区要么无区，
**同一列里两条陈述，谁说的完全看不出来**。而多源恰恰是这个组件唯一会被用到的场合。

## 为什么此前没有判据抓到

`HOTSPOT-07` 的 10 条判据用 `within(column).getByTestId(...)` 逐列查
`data-source-id`——它判的是「来源 id 在 DOM 里且没混列」。**那条判据是对的、也留着。**

但「在 DOM 里」与「在屏上」是两件事：读屏软件念不出一个属性，肉眼也看不见它。
所以本卡的判据取**渲染后的可见文本**（`NEVER 只断言 data-* 属性在`）。

呈现细节由 vitest 守（`web/components/source-columns/SourceColumns.test.tsx` 的既有 10 条
一条没动）。这里守三件它够不着的事：**词条齐**、**四个源一个不落**、**单据关掉了**。
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WEB = REPO / "web"
COMPONENT = WEB / "components" / "source-columns" / "SourceColumns.tsx"
NAMES = WEB / "components" / "source-columns" / "sourceName.ts"
SPEC = WEB / "components" / "source-columns" / "attribution.test.tsx"
ZH = WEB / "messages" / "zh.json"
EN = WEB / "messages" / "en.json"
SHEET = REPO / "docs" / "blocked" / "SOURCE-COLUMNS-DOES-NOT-SHOW-WHO-SAID-IT.md"
SOURCES_DIR = REPO / "flint" / "sources"


def _code_only(path: Path) -> str:
    text = re.sub(r"/\*[\s\S]*?\*/", "", path.read_text(encoding="utf-8"))
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("//")
    )


def _registered_sources() -> set[str]:
    """四个源的真相在 `flint/sources/*.py` 的 `source_id`，**不在前端**。"""
    found: set[str] = set()
    for path in SOURCES_DIR.glob("*.py"):
        found |= set(re.findall(r'source_id: str = "([^"]+)"',
                                path.read_text(encoding="utf-8")))
    return found


# ───────────────────────── 一、屏上写出了谁说的


def test_the_component_renders_a_visible_who() -> None:
    """来源名进的是**文本节点**，不是属性。"""
    code = _code_only(COMPONENT)

    assert 'data-testid="source-statement-who"' in code, "没有可见的来源名"
    assert "sourceName(s.sourceId)" in code, "屏上那一格不是从来源 id 来的"


def test_the_who_comes_before_the_statement() -> None:
    """署名在陈述**之前**。

    放在后面的话，读者会先形成判断再看署名——而署名正是用来形成那个判断的。
    """
    code = _code_only(COMPONENT)

    assert code.index("source-statement-who") < code.index("source-statement-text")


def test_the_existing_no_mixing_judgement_still_stands() -> None:
    """`data-source-id` 那条**原样留着**——它防的是混列，那是另一件事。

    改前那条判据是对的：它只是量不到「在不在屏上」。
    删掉它去换一条新的，等于用一个缺陷换另一个。
    """
    code = _code_only(COMPONENT)

    assert "data-source-id={s.sourceId}" in code


# ───────────────────────── 二、四个源一个不落，且认不出的原样显示


def test_every_registered_source_has_a_visible_name() -> None:
    """四个源（`gtrends` · `weibo` · `ghtrend` · `arxiv`）逐个有名字。

    真相取自 `flint/sources/*.py`——**新增一个源而前端没跟上，这里当场红**。
    抄一份清单在前端的话，两份会各自漂移。
    """
    table = NAMES.read_text(encoding="utf-8")
    zh = json.loads(ZH.read_text(encoding="utf-8"))
    en = json.loads(EN.read_text(encoding="utf-8"))

    registered = _registered_sources()
    assert len(registered) == 4, f"源的数量变了：{sorted(registered)}"
    for source_id in registered:
        assert f"{source_id}:" in table, f"{source_id} 在映射表里没有位置"
        key = f"source.name.{source_id}"
        assert key in zh and key in en, f"{key} 少了一侧词条"


def test_an_unknown_source_id_is_shown_verbatim() -> None:
    """**NEVER 编一个名字**，也 NEVER 显示成「未知来源」。

    前者假装我们认识它；后者把「我们没给这个源起过名」说成
    「这条陈述来路不明」——**那是两件事，而后一句会让读者丢掉一份真材料**。
    原样显示 id，读者至少知道是同一个源在说话。
    """
    code = _code_only(NAMES)

    assert "return key === undefined ? sourceId : t(key)" in code
    # 查的是**代码行**：注释里写着「NEVER 显示成未知来源」的那句话不是问题本身。
    # 拿整份文件去查，会把说明问题的那句话当成问题——本仓认得这个形状。
    for invented in ("未知来源", "unknown source", "其他来源"):
        assert invented not in code, f"代码里编了一个名字：{invented}"


def test_the_keys_are_written_out_not_assembled() -> None:
    """key **逐个写死**：拼出来的 key grep 不到，扫描器会把它报成未定义。

    第 7 批的 `JobDeniedNotice` 栽在同一处。
    """
    code = _code_only(NAMES)

    assert "`source.name." not in code, "key 是拼出来的"
    assert code.count('"source.name.') == 4


def test_proper_nouns_may_read_the_same_in_both_languages() -> None:
    """`GitHub Trending` 与 `arXiv` 中英同形——**那不是漏翻**。

    另两个必须不同：`Google 趋势` / `微博热搜` 有中文说法，
    中英同文才说明有一侧没翻。
    """
    zh = json.loads(ZH.read_text(encoding="utf-8"))
    en = json.loads(EN.read_text(encoding="utf-8"))

    for source_id in ("gtrends", "weibo"):
        key = f"source.name.{source_id}"
        assert zh[key] != en[key], f"{key} 中英同文——有一侧没翻"
    assert zh["source.name.ghtrend"] == en["source.name.ghtrend"]


# ───────────────────────── 三、合成句黑名单不倒 + 可见文本真的判到了


def test_no_synthesised_sentence_slipped_in() -> None:
    """既有判据的意思在这里再钉一次：这个组件**没有**任何汇总槽位。

    渲染层是最容易把「综合各方观点」那句话加回来的地方，
    而那句话没有任何一个来源支持它。
    """
    code = _code_only(COMPONENT)

    for banned in ("综合", "总体而言", "各方观点", "summary", "overall"):
        assert banned not in code, f"渲染层出现了合成句的痕迹：{banned}"


def test_the_visible_text_is_judged_by_rendering_not_by_attributes() -> None:
    """本卡的核心判据在 vitest 里（它才拿得到渲染后的文本）。

    这里把它拉进全局门，并检查它判的是**可见文本**而不是属性——
    只判 `data-*` 的话，改前那个缺陷照样是绿的。
    """
    spec = SPEC.read_text(encoding="utf-8")

    assert "textContent" in spec or "getByText" in spec, "判的还是属性"
    assert "data-source-id" not in spec or "textContent" in spec

    done = subprocess.run(
        ["npx", "vitest", "run", "components/source-columns"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=WEB, shell=True, timeout=900, check=False)

    assert done.returncode == 0, (done.stdout or "")[-3000:]


# ───────────────────────── 四、单据关掉


def test_the_sheet_is_closed() -> None:
    """卡上点名要关。**关单要写清关的理由**，NEVER 只把状态字改掉。"""
    assert SHEET.exists()
    lines = SHEET.read_text(encoding="utf-8").splitlines()

    assert lines[2].startswith("**状态** closed"), lines[2]
    assert "FIX-17" in SHEET.read_text(encoding="utf-8")
