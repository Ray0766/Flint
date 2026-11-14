"""FB-03：i18n key 泄漏到界面（终检 F-10）+ 「引用的 key 必须有定义」尺子。

## F-10 原话

全仓 115 个被 `t()` 引用的 key 里，**3 个在 `zh.json` 与 `en.json` 里都不存在**：

| 位置 | 用户实际看到 | 本该看到 |
|---|---|---|
| `QuoteSlot` 展开按钮 | 按钮上写着 `quote.expand_original` | 「展开原文」之类 |
| `RegionSwitch` 选择器标签 | 标签写着 `settings.region.label` | 「地区」之类 |
| `NativeName` 机翻标记 | 名字后跟着 `card.name.translated_mark` | 机翻标记文案 |

**前两处是该元素里唯一的文字**——不是角落里的小瑕疵，是**按钮和标签整个显示成了变量名**。

## 为什么没有尺子拦住

`tools/i18n_scan.mjs` 查的是「有没有中文硬编码」与 B7 静态规则，**不查「引用的 key 有没有定义」**；
三个组件自己的测试也没有断言这几处文案。**这个方向上此前没有任何检查。**

## DEC-009 救了这次（所以本卡 NEVER 改它）

`t()` 在 key 缺失时返回 **key 本身**并 `console.warn`，不返回空串。终检原话：
「这条设计救了这次——正因为它显眼，才被我一眼抓到」。空串会变成界面上一块**无声的空白**，
没人会发现。本卡把这条行为也钉成断言，防止有人「顺手」改成返回空串把界面弄干净。
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WEB = REPO / "web"
TOOL = REPO / "tools" / "i18n_key_defined.mjs"
ZH = WEB / "messages" / "zh.json"
EN = WEB / "messages" / "en.json"

# 终检点名的三处（本卡要修好的）。
LEAKED_KEYS = (
    "card.name.translated_mark",
    "quote.expand_original",
    "settings.region.label",
)


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    node = shutil.which("node")
    assert node is not None, "找不到 node：这条门量不了，NEVER 当它通过"
    return subprocess.run([node, str(TOOL), *args], cwd=REPO, capture_output=True,
                          text=True, encoding="utf-8", check=False)


def _catalog(path: Path) -> dict[str, str]:
    return json.loads(path.read_text(encoding="utf-8"))


# ───────────────────────── acceptance①：三处修好


def test_the_three_leaked_keys_are_now_defined_on_both_sides() -> None:
    """三个 key 在 zh 与 en **两侧都有定义**——只补一侧会让另一侧继续显示变量名。"""
    zh, en = _catalog(ZH), _catalog(EN)

    for key in LEAKED_KEYS:
        assert key in zh, f"zh.json 仍缺 {key}"
        assert key in en, f"en.json 仍缺 {key}"
        assert zh[key].strip() and en[key].strip(), f"{key} 补了个空串"
        assert zh[key] != key and en[key] != key, f"{key} 的文案就是 key 本身，等于没补"


def test_the_two_catalogs_stay_symmetric() -> None:
    """补完之后键集仍然逐个一致（I18N 那条不变量）。"""
    zh, en = set(_catalog(ZH)), set(_catalog(EN))

    assert zh == en, f"键集不对称：zh 多 {sorted(zh - en)}，en 多 {sorted(en - zh)}"


def test_the_chinese_and_english_texts_are_not_the_same_string() -> None:
    """补的是两种语言的文案，不是把中文抄进 en.json。

    抄一份进去，键集对称与「有定义」两条都会绿，而英文用户看到的是中文——
    那正是这三条断言里最容易蒙混过去的一条。
    """
    zh, en = _catalog(ZH), _catalog(EN)

    for key in LEAKED_KEYS:
        assert zh[key] != en[key], f"{key} 的中英文案是同一个字符串"
        assert not any("一" <= ch <= "鿿" for ch in en[key]), (
            f"en.json 里 {key} 含中文：{en[key]!r}"
        )


# ───────────────────────── acceptance②：尺子


def test_the_repo_has_no_referenced_key_without_a_definition() -> None:
    """全仓扫描：每个被 `t()` 引用的 key 在两份词条里都有定义。"""
    done = _run("web")

    assert done.returncode == 0, done.stdout + done.stderr


def test_the_scanner_names_the_key_and_the_file_line() -> None:
    """报红时点名 key **与文件行号**——只说「有 key 缺定义」等于把定位活退回给人。"""
    report = json.loads(_run("web", "--json").stdout)

    assert report["schema"] == "i18n-key-defined/1"
    assert report["missing"] == []
    assert report["referenced"] >= 100, f"只扫到 {report['referenced']} 个引用，扫描面塌了"
    sample = report["references"][0]
    assert {"key", "file", "line"} <= set(sample)
    assert sample["file"].endswith((".ts", ".tsx"))
    assert sample["line"] >= 1


def test_a_component_referencing_an_undefined_key_is_red(tmp_path: Path) -> None:
    """acceptance④ 阴性对照：构造一个引用未定义 key 的组件 → 尺子必须红并点名。"""
    comp = tmp_path / "Bad.tsx"
    comp.write_text('import { t } from "x";\nexport const B = () => <b>{t("nope.not.defined")}</b>;\n',
                    encoding="utf-8")

    done = _run(str(tmp_path), "--messages", str(WEB / "messages"))

    assert done.returncode == 1
    assert "nope.not.defined" in done.stdout + done.stderr
    assert "Bad.tsx" in done.stdout + done.stderr


def test_an_all_defined_directory_passes(tmp_path: Path) -> None:
    """正例：全部有定义 → exit 0。见谁都报红的尺子同样量不出东西。"""
    key = next(iter(_catalog(ZH)))
    comp = tmp_path / "Good.tsx"
    comp.write_text(f'export const G = () => <b>{{t("{key}")}}</b>;\n', encoding="utf-8")

    assert _run(str(tmp_path), "--messages", str(WEB / "messages")).returncode == 0


def test_test_files_are_skipped_so_the_missing_key_fixture_survives() -> None:
    """测试文件不算：`t()` 的缺键路径本来就要拿一个不存在的 key 当夹具。

    把夹具算成缺陷，等于逼着测试删掉自己的反例——那条反例守的正是 DEC-009。
    """
    report = json.loads(_run("web", "--json").stdout)
    files = {ref["file"] for ref in report["references"]}

    assert not any(".test." in f for f in files), "扫到了测试文件里的引用"
    assert any("nope" in ref["key"] for ref in report["references"]) is False


def test_the_scanner_reports_but_does_not_fail_on_unused_keys() -> None:
    """定义了却没被引用的键**只报不判红**（F-10 原话：不是缺陷，是清理线索）。

    把它判红会逼人删掉将来要用的文案，或者反过来给不用的键硬造一个引用。
    """
    report = json.loads(_run("web", "--json").stdout)

    assert "unused" in report
    assert isinstance(report["unused"], list)
    assert _run("web").returncode == 0, "有未引用键时不该红"


def test_a_dynamic_key_is_judged_by_its_prefix_not_skipped() -> None:
    """动态 key（`t(f"graph.role.{role}")` 那种）按**静态前缀**判，NEVER 跳过。

    跳过等于给自己开一个盲区，而盲区正是这把尺子要治的病。仓库里三处合法动态 key
    （`graph.role.*` 有 5 个候选、`workbench.tab.*` 有 2 个、`export.format.*` 有 5 个、
    `locale.lang.*` 有 2 个）
    必须被认成动态而不是缺失——
    本工具第一版就把它们报成了缺失，是实测把这一档逼出来的。
    """
    report = json.loads(_run("web", "--json").stdout)
    prefixes = {row["prefix"] for row in report["dynamic"]}

    # 判**等值**是有意的：动态 key 是这把尺子唯一看不透的一档，多出一个就该有人
    # 来这里确认「它的候选值全都有定义」。UI-02 加 `export.format.*` 时就是这么被拦下来确认的。
    # UI-07 加了第四处 `locale.lang.*`（zh / en 两个候选）；
    # UI-11 加了第五处 `overview.*`（topics / jobs / deliverables 三个候选）。
    # 照这条判据自己写的规矩——多一个前缀就来这里确认它的候选值全都有定义。
    # DS-03 加了第六处 `enum.*`：七族 37 个候选，中英各一份，
    # 且每族的成员**从冻结件/后端源码解析后判等**（`tests/v041/test_enum_labels.py`）——
    # 那把尺子比这里更硬，这里只确认前缀在册、候选非空。
    # CHAIN-05 加了第七处 `proposal.audience.*`：两个候选（`human_reader` /
    # `ai_executor`），且**没有默认值**（后端原话 `audience is mandatory with no default`）。
    # 两个候选的文案中英各一份，下面那条循环会确认它们真的在词典里。
    # SHELL-02 加了第八处 `theme.*`：三个候选（`system` / `light` / `dark`），
    # 与 `flint/profile/prefs.py#_THEMES` 一一对应。**候选表的唯一真相在后端**，
    # 这里只确认前缀在册、候选非空——三态是不是这三个由那边的判据管
    # （`tests/v041/test_theme_toggle.py`）。
    #
    # 这一条是 SHELL-02 收卡时**漏掉的红**：那一轮只跑了自己那个判据文件，
    # 没跑全量，于是这把尺子的红被带进了下一张卡才发现。
    # 教训写在这里而不是只写在 trace 里：下一个加 `t(\`x.${…}\`)` 的人会先读到它。
    # `WB-05`/`WB-06` 加了第九、十、十一处，三处都来自**同一张章节表**：
    #   `wb.section.<模板>.<章节>`  章名（照蓝本逐字，34 个候选）
    #   `wb.check.<模板>.<章节>`    逐章检查问句（**由 `tools/gen_section_tables.py`
    #                               从 `assets/templates/*.yaml` 生成**，34 个候选）
    #   `wb.template.<模板>`        五套模板自己的名字
    # 前两处按模板分键是必需的：同一个 `timeline` 在基金申请里叫「时间表」、
    # 在论文开题里叫「时间线」——压成一个键，其中一套会显示另一套的名字。
    # 候选表的唯一真相在 yaml 与蓝本，由 `tests/v041/test_wb_sections.py` 逐字比对；
    # 这里照这条判据自己的规矩，只确认前缀在册、候选非空。
    # `JUDGE-TAB-01` 加了第十二处 `judge.tabs.`：五个 tab 名由 `tab.key` 取，
    # 候选就是那五个键（`JudgeTabKey` 那个联合类型），
    # 由 `tests/v041/test_judge_tabs.py` 逐条比对；这里照规矩只确认前缀在册、候选非空。
    assert prefixes == {
        "graph.role.", "workbench.tab.", "export.format.", "locale.lang.",
        "overview.", "enum.", "proposal.audience.", "theme.",
        "wb.section.", "wb.check.", "wb.template.", "judge.tabs.",
        # `AUD-PACK-01` 加的第十三处 `proposal.submit.`：按钮文案随受众变，
        # 候选就是那两个受众值（`human_reader` / `ai_executor`，后端
        # `flint/api/compose.py` 的 `Literal[...]` 是唯一真相），
        # 外加未选时那一句 `proposal.submit.unpicked`。
        "proposal.submit."}
    assert all(row["absent_in"] == [] for row in report["dynamic"])
    assert not any("${" in row["key"] for row in report["missing"])

    zh = _catalog(ZH)
    for prefix in prefixes:
        assert [k for k in zh if k.startswith(prefix)], f"{prefix} 下一个候选都没有"


def test_a_dynamic_key_with_no_candidate_is_red(tmp_path: Path) -> None:
    """反向：前缀下一个定义都没有的动态 key = 真泄漏，判红。

    没有这一条，上一条就成了「动态 key 一律放行」——那与跳过没有区别。
    """
    comp = tmp_path / "Dyn.tsx"
    comp.write_text("export const D = (x) => t(`nothing.here.${x}`);\n", encoding="utf-8")

    done = _run(str(tmp_path), "--messages", str(WEB / "messages"))

    assert done.returncode == 1
    assert "nothing.here." in done.stdout + done.stderr


# ───────────────────────── acceptance③：DEC-009 的行为不许被改掉


def test_a_missing_key_still_renders_the_key_itself_not_an_empty_string() -> None:
    """DEC-009：缺键时返回 **key 本身** 并告警，NEVER 返回空串。

    空串会变成界面上一块无声的空白，没人会发现；而一个显眼的 `quote.expand_original`
    一眼就能被抓到——**这条设计正是 F-10 被发现的原因**。
    """
    source = (WEB / "lib" / "i18n" / "t.ts").read_text(encoding="utf-8")

    assert "return key" in source.replace(" ", "").replace("returnkey", "return key"), (
        "t() 不再返回 key 本身了"
    )
    assert 'return ""' not in source and "return ''" not in source, "t() 出现了返回空串的路径"
    assert "warn" in source, "缺键不再告警"
