"""GAUGE-08 · 换行符：一个 CRLF 就能让全仓剥注释的尺子集体失效。

## 这把尺子守的不是代码风格，是**别的尺子的视力**

全仓「先剥注释再判」的尺子共用同一份剥刀：

```js
source.split("\\n").map((line) => line.replace(/\\/\\/.*$/, "")).join("\\n")
```

CRLF 之下，`split("\\n")` 切出来的每行**末尾还挂着一个 `\\r`**。
JS 正则里 **`\\r` 是行终止符**：`.` 不匹配它，`$`（无 `m`）要求匹配到字符串末尾。
于是 `//.*$` 在 `\\r` 前就走不下去，**整行注释一条都剥不掉**。

## 本卡开工时的实测（真文件，不是构造的）

```
lib/jobClient.ts      CRLF 161 行   注释 13 处   剥掉 0 处
lib/screenClient.ts   CRLF  80 行   注释 26 处   剥掉 0 处
web/ 下 198 个 ts/tsx —— 35 个是 CRLF
```

那 35 个文件上，所有「源码里不该出现 X」的判据都退化成了
「**全文**里不该出现 X」——一次表现为假红（`DEF-03` 撞上的那次），
同一条缝在另一个方向上给出**假绿**。

修完之后同一份探针：`剥掉 13 处 / 26 处`。

## 根因写成会跑的判据

卡面 acceptance② 点名了这条：**测试要构造一份 CRLF 文件并断言剥注释失效被检出**。
所以下面有一条真去跑 `node` 的判据——只在 Python 里描述根因是不够的，
那等于把「JS 正则怎么理解 `\\r`」这件事当成了共识。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tools.check_line_endings import SCANNED_FACES, audit, classify

REPO = Path(__file__).resolve().parents[2]
RULER = REPO / "tools" / "check_line_endings.py"
TICKET = REPO / "docs" / "blocked" / "CRLF-BREAKS-COMMENT-STRIPPING.md"

_STRIPPER = (
    'const codeOnly = (s) => s.split("\\n")'
    '.map((l) => l.replace(/\\/\\/.*$/, "")).join("\\n");'
)


# ───────────────────────── acceptance①：尺子建出来且报得准


def test_the_scanned_face_is_not_empty() -> None:
    """扫描面为空**不是「干净」**，是没量到。

    这条放在最前面：下面所有「0 处违规」的断言，
    在扫描面塌掉时都会假绿。
    """
    report = audit()

    assert report["scanned"] > 100, f"只扫到 {report['scanned']} 个文件：扫描面塌了"


def test_the_scanned_face_is_where_the_strippers_actually_look() -> None:
    """守的是**剥刀实际扫描的那个面**，不是全仓风格。

    本仓 500 多个文件是纯 CRLF（Windows 常态）。一刀切成 LF 是一次巨大的
    无关改动，且会让所有历史比对失效。所以只盯 `web/**/*.ts(x)`——
    `codeOnly` / `i18n_scan.mjs` / `check_design_constraints.mjs` 都扫这一面。
    """
    assert SCANNED_FACES == (("web", (".ts", ".tsx")),)


def test_the_repository_is_consistent_now() -> None:
    report = audit()

    assert report["findings"] == [], [f["path"] for f in report["findings"]][:6]


def test_a_crlf_file_is_reported_with_its_name(tmp_path: Path) -> None:
    """**阴性对照**：造一个 CRLF 文件 → 判红并**指出是哪个文件**。

    只说「有文件行尾不对」等于把定位活退回给人。
    """
    (tmp_path / "web").mkdir()
    bad = tmp_path / "web" / "bad.ts"
    bad.write_bytes(b'// note\r\nexport const x = 1;\r\n')

    report = audit(tmp_path)
    paths = {f["path"] for f in report["findings"]}

    assert "web/bad.ts" in paths
    row = next(f for f in report["findings"] if f["path"] == "web/bad.ts")
    assert row["kind"] == "crlf"
    assert "剥不掉" in row["detail"], "报了却没说清后果"


def test_a_mixed_file_is_reported_as_its_own_kind(tmp_path: Path) -> None:
    """混用单列一类——它通常是**一次工具事故的痕迹**。

    `Path.write_text()` 在 Windows 上默认做换行翻译：读进来的 `\\n`
    写回去变成 `\\r\\n`。`DEF-03` 那次就是这么来的：文件内容逐字未变，
    行尾全变了。
    """
    (tmp_path / "web").mkdir()
    bad = tmp_path / "web" / "half.ts"
    bad.write_bytes(b'const a = 1;\r\nconst b = 2;\n')

    row = next(f for f in audit(tmp_path)["findings"] if f["path"] == "web/half.ts")

    assert row["kind"] == "mixed"
    assert "工具事故" in row["detail"]


def test_an_all_lf_file_passes(tmp_path: Path) -> None:
    """正例：见谁都报红的尺子同样量不出东西。"""
    (tmp_path / "web").mkdir()
    (tmp_path / "web" / "ok.ts").write_bytes(b"const x = 1;\nconst y = 2;\n")

    assert audit(tmp_path)["findings"] == []


def test_classify_tells_the_three_shapes_apart() -> None:
    assert classify(b"a\nb\n") == "lf"
    assert classify(b"a\r\nb\r\n") == "crlf"
    assert classify(b"a\r\nb\n") == "mixed"
    assert classify(b"single line no newline") == "none"


# ───────────────────────── acceptance②：根因写成会跑的判据


def test_the_js_stripper_really_fails_on_crlf(tmp_path: Path) -> None:
    """**真跑 `node`**：同一份剥刀，LF 下剥得掉，CRLF 下一条都剥不掉。

    只在 Python 里描述根因是不够的——那等于把「JS 正则怎么理解 `\\r`」
    这件事当成共识。这条让 `node` 自己说话。
    """
    node = shutil.which("node")
    if node is None:
        pytest.skip("找不到 node：这条量不了，NEVER 当它通过")

    probe = tmp_path / "probe.mjs"
    probe.write_text(
        _STRIPPER + "\n"
        'const lf = "// note\\nconst x = 1;\\n";\n'
        'const crlf = lf.replace(/\\n/g, "\\r\\n");\n'
        "const count = (s) => (s.match(/\\/\\//g) || []).length;\n"
        "console.log(JSON.stringify({\n"
        "  lfStripped: count(lf) - count(codeOnly(lf)),\n"
        "  crlfStripped: count(crlf) - count(codeOnly(crlf)),\n"
        "}));\n",
        encoding="utf-8", newline="\n")

    out = subprocess.run([node, str(probe)], capture_output=True, text=True,
                         encoding="utf-8", check=False).stdout
    result = json.loads(out)

    assert result["lfStripped"] == 1, "LF 下都剥不掉？那把剥刀本身坏了"
    assert result["crlfStripped"] == 0, (
        "CRLF 下居然剥掉了——根因描述过期了，去更新本卡与那张单"
    )


def test_the_ruler_explains_the_root_cause_not_just_the_symptom() -> None:
    """尺子自己要讲清**为什么**，而不是只说「行尾不一致」。

    只报症状的话，下一个人会以为这是代码风格，
    然后把这把尺子关掉——而它守的是别的尺子的视力。
    """
    text = RULER.read_text(encoding="utf-8")

    assert "行终止符" in text
    assert "剥刀" in text or "剥注释" in text
    assert "假绿" in text, "没说清另一个方向上的后果"


# ───────────────────────── acceptance③：接进全局门 + .gitattributes 评估


def test_this_gate_runs_inside_pytest_q() -> None:
    """**不在门里的尺子等于没有**（F-11 的教训）。

    判的是 pytest 的**默认收集面**收不收得到本文件——
    而不是读源码找 `skipif` 那种写法（`WIRE-05` 那次实测：
    读源码会判到自己的断言串上）。
    """
    done = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q",
         "-k", "the_repository_is_consistent_now"],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", check=False)

    assert done.returncode == 0, done.stdout[-400:]
    assert "test_the_repository_is_consistent_now" in done.stdout


def test_the_cli_runs_and_says_something_useful() -> None:
    done = subprocess.run(
        [sys.executable, str(RULER)], cwd=REPO,
        capture_output=True, text=True, encoding="utf-8", check=False)

    assert done.returncode == 0, done.stdout[-400:]
    assert "行尾一致" in done.stdout


def test_the_git_attributes_question_is_answered_not_skipped() -> None:
    """`.gitattributes` 这一项**要有结论**，NEVER 悄悄略过（卡面 acceptance③）。

    本仓不是 git 仓库（`git rev-parse` 不通），所以 `.gitattributes` 无处生效——
    结论写进 trace 并由本条钉住。哪天它变成 git 仓库，这条会红，
    提醒那时的人去加 `* text=auto eol=lf`。
    """
    done = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"], cwd=REPO,
        capture_output=True, text=True, encoding="utf-8", check=False)
    is_git = done.returncode == 0 and done.stdout.strip() == "true"

    if is_git:
        attributes = REPO / ".gitattributes"
        assert attributes.exists(), (
            "本仓已经是 git 仓库了——去加 .gitattributes（`* text=auto eol=lf`），"
            "否则 checkout 会把行尾又翻回 CRLF，这把尺子每次都红"
        )
    else:
        assert not (REPO / ".gitattributes").exists(), (
            "非 git 仓库却有 .gitattributes——它不会生效，留着是误导"
        )


def test_the_ticket_is_closed() -> None:
    head = "\n".join(TICKET.read_text(encoding="utf-8").splitlines()[:16])

    assert "已关闭" in head
    assert "GAUGE-08" in head
