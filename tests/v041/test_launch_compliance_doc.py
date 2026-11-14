"""COMP-01：上线前合规手续清单单独成文（owner 2026-08-04 裁决：手续单独立档）。

## 这张卡在防什么

`docs/blocked/K2-COMPLIANCE-BEFORE-LAUNCH.md` 里原本自带一张**手抄的**逐源表。
`assets/source_legal_status.yaml` 是实测产物，它会随重测变；手抄的那张不会。
两处各写一份 = 迟早各说各的，而**读的人分不出哪份是真的**——尤其它决定的是
「上线那天要不要停下来办手续」。

所以本卡的形状是：

1. 逐源表**由数据生成**（`__main__` 出，判据逐字比），人只写两列人读的内容；
2. 问题单那份表**删掉**，顶部换成指针——单一入口，漂不起来；
3. 新增源而清单没跟上时，生成器**抛错**，判据跟着红。

## 五列里哪两列是人写的

`source_id` / `robots 实测态` / `派生合规态` 三列全部来自
`assets/source_legal_status.yaml` 与 `flint/region/legal_probe.py#derive_fetch_legal_status`。
**上线前要办的手续**与**办成的判据**两列是人写的——它们要说的是「去签哪份约、
读哪条款、结论写到哪个文件里」，那不是数据里有的东西。人写的两列钉在本文件的
`FORMALITIES` 里：写在测试文件而不是文档里，是为了让「文档 = 数据 + 这张表」
这句话可以被逐字验证。

## 判据不是「文档里有这个词」

每一行的「办成的判据」都必须给出**一个可以去看的地方**（反引号里的路径或代码符号）。
只写「确认合规」的判据等于没有判据：上线那天没人知道该看哪里才算办成了。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# pytest 由 `pythonpath = ["."]` 供仓根；`__main__` 直跑本文件时没有。
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from flint.region.legal_policy import RECORD_ONLY
from flint.region.legal_probe import (
    MeasuredStatus,
    derive_fetch_legal_status,
    load_measured_status,
)

DOC = REPO / "docs" / "上线前合规手续清单.md"
BLOCKED = REPO / "docs" / "blocked" / "K2-COMPLIANCE-BEFORE-LAUNCH.md"

TABLE_OPEN = "<!-- 表由 tests/v041/test_launch_compliance_doc.py 的 __main__ 生成，NEVER 手改 -->"
TABLE_CLOSE = "<!-- 表到此为止 -->"

HEADER = "| source_id | robots 实测态 | 派生合规态 | 上线前要办的手续 | 办成的判据 |"
RULER = "|---|---|---|---|---|"

# 人写的两列。新增源时这里没有对应项 → `build_table` 抛错 → 判据红。
FORMALITIES: dict[str, tuple[str, str]] = {
    "gtrends": (
        "人读 Google ToS 的自动化取数条款，结论落 `docs/legal/tos-readings/google.md`",
        "`docs/legal/tos-readings/google.md` 存在，写明结论、裁决人、日期",
    ),
    "google_trends_api": (
        "同 `gtrends`（同一主机同一条款）；另确认官方 API 的配额与端点档位",
        "`docs/legal/tos-readings/google.md` 里单列一节写明 API 档位与配额",
    ),
    "weibo": (
        "人读微博 ToS 的自动化取数限制并留结论——robots 放行不代表条款放行",
        ("`docs/legal/tos-readings/weibo.md` 给出「准 / 不准」二选一；判不准则该源"
         "在种子表填 `restricted` 并走 E6 缺数据行"),
    ),
    "yahoo_jp_realtime": (
        "排行 API 面向合作方，走商务申请（K1-01 第 2 问）",
        "获批回执存 `docs/legal/contracts/yahoo-jp.md`，含申请编号与生效日期",
    ),
    "ghtrend": (
        "确认 GitHub API ToS 的商用条款与速率限制档位",
        "`docs/legal/tos-readings/github.md` 写明商用是否放行与所在速率档",
    ),
    "arxiv": (
        "arXiv 的 API Terms of Use 与 robots 是两个口径，须 owner 裁决以哪个为准",
        ("`docs/legal/tos-readings/arxiv.md` 写明以哪个口径为准；裁为放行则重跑 "
         "`harness/probe_robots.py` 并让 `assets/source_legal_status.yaml` 带上新一次实测"),
    ),
    "naver_datalab": (
        "开 Naver 开发者账号并确认商用条款",
        "账号与商用条款回执存 `docs/legal/contracts/naver.md`，含开发者应用 ID",
    ),
    "reddit_data_api": (
        "免费档仅限非商业，商用须另签数据 API 合同（K1-01 第 2 问）",
        "合同回执存 `docs/legal/contracts/reddit.md`，含合同编号与配额档",
    ),
}


def build_table(entries: dict[str, MeasuredStatus] | None = None) -> str:
    """按实测记录 + `FORMALITIES` 生成整张表。

    表里没有的源直接抛 `KeyError`：**新增源而手续没写就该停下来**，
    NEVER 给它填一行「待定」——那一行在上线清单上与「已办」长得一样。
    """
    measured = entries if entries is not None else load_measured_status()
    rows = [HEADER, RULER]
    for source_id in sorted(measured):
        entry = measured[source_id]
        if source_id not in FORMALITIES:
            raise KeyError(
                f"{source_id} 在实测记录里，但上线清单没有它的手续与判据："
                "新增源时两列人写的内容要一起补上")
        formality, evidence = FORMALITIES[source_id]
        rows.append(
            f"| `{source_id}` | {entry.state} | {derive_fetch_legal_status(entry)} "
            f"| {formality} | {evidence} |")
    return "\n".join(rows)


def _doc() -> str:
    return DOC.read_text(encoding="utf-8")


def _table_in_doc() -> str:
    body = _doc()
    start = body.find(TABLE_OPEN)
    end = body.find(TABLE_CLOSE)
    assert start != -1 and end > start, "文档里找不到成对的表标记"
    return body[start + len(TABLE_OPEN):end].strip()


def _rows_in_doc() -> list[list[str]]:
    return [
        [cell.strip() for cell in line.strip().strip("|").split("|")]
        for line in _table_in_doc().splitlines()[2:]
    ]


# ───────────────────────── 一、五列逐源、数据取自 YAML（acceptance①）


def test_the_document_exists() -> None:
    assert DOC.exists(), f"没有 {DOC.name}"


def test_the_table_is_exactly_what_the_data_produces() -> None:
    """acceptance①：文档里那张表**逐字**等于数据生成的那张。

    这是「NEVER 手抄」唯一可执行的形式：改一个字就红。只判「表里有这些源」的话，
    把 `disallowed` 手抖写成 `allowed` 照样绿——而那正是上线那天会出事的那种错。
    """
    assert _table_in_doc() == build_table(), (
        "文档里的表与数据对不上：用 __main__ 重新生成，NEVER 手改")


def test_the_table_has_the_five_columns_the_card_names() -> None:
    assert _table_in_doc().splitlines()[0] == HEADER
    assert len(HEADER.strip("|").split("|")) == 5


def test_every_measured_source_has_a_row_and_no_row_is_invented() -> None:
    """逐条对齐：数据里有的都在表里，表里有的都在数据里。"""
    measured = set(load_measured_status())
    in_doc = {row[0].strip("`") for row in _rows_in_doc()}

    assert in_doc == measured, f"多出来的：{in_doc - measured}；漏掉的：{measured - in_doc}"


def test_the_derived_column_comes_from_the_code() -> None:
    """派生合规态由 `derive_fetch_legal_status` 算，NEVER 在文档里另写一套映射。"""
    measured = load_measured_status()

    for row in _rows_in_doc():
        source_id = row[0].strip("`")
        assert row[1] == measured[source_id].state, f"{source_id} 的实测态与数据不符"
        assert row[2] == derive_fetch_legal_status(measured[source_id]), (
            f"{source_id} 的派生态与代码算出来的不符")


def test_the_restricted_sources_are_the_ones_the_data_says() -> None:
    """`restricted` 那几个由数据决定，且**必须真的有**——一个都没有时报红。

    一个都没有意味着要么数据被洗白了，要么派生逻辑坏了。上线清单上
    「没有受限源」是个需要被证明的结论，不是默认值。
    """
    measured = load_measured_status()
    expected = {sid for sid, e in measured.items() if derive_fetch_legal_status(e) == "restricted"}
    in_doc = {row[0].strip("`") for row in _rows_in_doc() if row[2] == "restricted"}

    assert expected, "实测记录里一个 restricted 都没有——这需要证明，不该是默认值"
    assert in_doc == expected


def test_a_new_source_without_formalities_stops_the_build() -> None:
    """acceptance③ 的机械形态：新增源而清单没跟上 → 生成器抛错 → 上面那条判据红。"""
    measured = dict(load_measured_status())
    sample = next(iter(measured.values()))
    measured["a_brand_new_source"] = MeasuredStatus(
        source_id="a_brand_new_source", robots_url=sample.robots_url,
        state=sample.state, evidence=sample.evidence, probed_on=sample.probed_on,
        tos_url=sample.tos_url,
    )

    try:
        build_table(measured)
    except KeyError as err:
        assert "a_brand_new_source" in str(err)
    else:
        raise AssertionError("新增源没有手续，生成器却照出了表")


def test_every_row_names_a_place_to_look() -> None:
    """每一行的「办成的判据」都要给出**一个可以去看的地方**。

    只写「确认合规」的判据等于没有判据：上线那天没人知道该看哪里才算办成了。
    """
    for row in _rows_in_doc():
        assert row[3], f"{row[0]} 没写要办的手续"
        assert re.search(r"`[^`]+`", row[4]), f"{row[0]} 的判据里没有可以去看的地方：{row[4]}"


# ───────────────────────── 二、触发条件与失效条件（acceptance②）


def _section_body(title: str) -> str:
    """取某个二级标题下的正文，**不含标题行本身**。

    不含标题行是判据的一部分：标题「失效条件（现行裁决什么时候不再覆盖）」里
    就带着「不再覆盖」四个字，连标题一起判的话，正文写成「继续有效」也照样绿
    （变异考⑤ 实测）。
    """
    body = _doc()
    start = body.find(f"## {title}")
    assert start != -1, f"文档里没有「{title}」这一节"
    end = body.find("\n## ", start + 1)
    return body[start:end if end != -1 else len(body)].split("\n", 1)[1]


def test_the_doc_states_the_trigger_in_its_own_section() -> None:
    """触发条件判在**触发条件那一节**里。

    按「文档头三十行里有『商用上线』」判的话，失效条件那节顺口再提一次就把它喂饱了
    ——把触发条件整句删掉毫无反应（变异考④ 实测）。
    """
    assert "商用上线" in _section_body("触发条件")


def test_the_doc_states_when_the_decision_stops_covering() -> None:
    """失效条件同理，判在那一节的正文里。"""
    body = _section_body("失效条件（现行裁决什么时候不再覆盖）")

    assert "不再覆盖" in body, "失效条件那一节没写它什么时候不再覆盖"
    assert "flint/region/legal_policy.py#RECORD_ONLY" in body, "没指向那条机读裁决"


def test_every_scope_string_in_the_doc_is_the_one_in_the_code() -> None:
    """`scope` 逐字取自 `RECORD_ONLY`：代码里改了范围，文档没跟上就红。

    判的是**文档里每一处** `scope="…"`，不是「有一处对得上」：文档里写了两处，
    只改其中一处照样绿——那是「一半文档已经在说另一件事」的状态（变异考⑥ 实测）。
    判在代码读出来的那个字符串上，NEVER 把 `non_commercial` 手抄进判据——
    手抄的判据和手抄的文档一起漂，两边一致地错。
    """
    found = re.findall(r'scope="([a-z_]+)"', _doc())

    assert found, "文档里一处都没写现行裁决的范围"
    assert set(found) == {RECORD_ONLY.scope}, f"文档里的 scope 与代码不符：{sorted(set(found))}"
    assert RECORD_ONLY.decided_on.isoformat() in _doc(), "没写这条裁决是哪天做的"


# ───────────────────────── 三、唯一入口，问题单不再各写一份（acceptance④）


def test_the_blocked_doc_points_here_from_the_top() -> None:
    """问题单顶部指过来。"""
    head = "\n".join(BLOCKED.read_text(encoding="utf-8").splitlines()[:12])

    assert "上线前合规手续清单.md" in head, "问题单顶部没有指向清单的指针"


def test_the_blocked_doc_no_longer_carries_its_own_per_source_list() -> None:
    """acceptance④：**两处 NEVER 各写一份**。问题单里那张逐源表要删掉。

    判的是「问题单里不再逐源列 robots 结论」，不是「不许提源的名字」——
    它讲怎么切档时提到某个源是正常的。所以钉在**成行的表**上：
    问题单里 NEVER 再出现一行同时带 `|` 与两个及以上源名/合规态的表行。
    """
    body = BLOCKED.read_text(encoding="utf-8")
    measured = set(load_measured_status())

    offenders = [
        line for line in body.splitlines()
        if line.strip().startswith("|")
        and (any(f"`{sid}`" in line for sid in measured)
             or ("allowed" in line and "restricted" in line))
    ]

    assert offenders == [], "问题单里还留着第二份逐源清单：" + " / ".join(offenders[:3])


def test_the_switch_back_procedure_is_still_reachable() -> None:
    """切档那一步不能在搬家时丢掉：两份文档合起来必须还讲得出怎么切回 `BLOCK`。"""
    both = BLOCKED.read_text(encoding="utf-8") + _doc()

    assert "OWNER_DECISION" in both and "BLOCK" in both


# ───────────────────────── 表生成（`python tests/v041/test_launch_compliance_doc.py`）

if __name__ == "__main__":  # pragma: no cover - 生成入口，pytest 不走这里
    body = _doc() if DOC.exists() else ""
    table = build_table()
    if TABLE_OPEN in body and TABLE_CLOSE in body:
        head = body[: body.find(TABLE_OPEN) + len(TABLE_OPEN)]
        tail = body[body.find(TABLE_CLOSE):]
        DOC.write_text(f"{head}\n{table}\n{tail}", encoding="utf-8")
        print(f"表已重生成 → {DOC}")
    else:
        print(TABLE_OPEN)
        print(table)
        print(TABLE_CLOSE)
