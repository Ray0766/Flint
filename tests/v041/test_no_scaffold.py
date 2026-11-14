"""FB-10：清 A 类脚手架 + 一把不让它漂回来的尺子。

## A 类与诚实态的分界（acceptance③④ 的正题）

**A 类脚手架 = 开发要看的东西跑到了产品面上**：端点路径、内部文件路径、
block/section 内部 id、schema 字段名、`X-User-Id` / `demo-user`。
它们对用户毫无意义，只会让人以为产品还没做完。

**诚实态不是脚手架，一条都不许删**：哪块被阻断导出、哪个数字有出处、
哪条陈述有争议、哪处「接口未提供」——这些是**产品需求**，用户有权看见。
两者的分界就是这把尺子的全部难点，所以它配了**两组对照**：
命中组（构造六种脚手架，必须红）与不误伤组（构造六种诚实态，必须放行）。

## 先 B 后 A 的次序（acceptance③）

本卡依赖 FB-09。**先删 A 类会得到一个更干净但更空洞的界面**——
id 换不成内容，删了就什么都不剩。所以顺序是：先把六类 id 接上内容（FB-09），
再把纯脚手架清掉（本卡）。

## 实况：代码层本来就是干净的

扫下来 `web/` 的**代码层**（剥注释后）零命中——端点路径、文件路径、`demo-user`
都只出现在注释里。所以本卡真正的产物是**尺子**：让它 NEVER 漂回来。
`field_path` 是唯一一处「看起来像 schema 字段名」的可见文本，但它是
**ProfileRef 出处通道**（第三条通道，说的是这个数字来自档案里的哪一项），
删了就是删掉出处——按 acceptance④ 保留，并在尺子里**显式登记为例外**（带理由），
NEVER 悄悄放行。
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TOOL = REPO / "tools" / "no_scaffold_on_screen.mjs"

# 命中组：每一条都是「开发要看的东西跑到了产品面」。
SCAFFOLD_CASES = {
    "端点路径": 'export const A = () => <p>GET /deliverables/{id}/blocks</p>;',
    "内部文件路径": 'export const B = () => <p>见 flint/api/deref.py 的实现</p>;',
    "X-User-Id": 'export const C = () => <p>X-User-Id: demo-user</p>;',
    "demo 用户": 'export const D = () => <span>{"demo-user"}</span>;',
    "内部 block id": "export const E = ({ b }) => <p>{b.block_id}</p>;",
    "内部 section id": "export const F = ({ s }) => <p>{s.section_id}</p>;",
}

# 不误伤组：每一条都是**产品需求**，尺子放行才算对。
HONEST_CASES = {
    "争议记号": 'export const G = () => <span className="mark mark--disputed" />;',
    "阻断导出": 'export const H = () => <p>{t("export.blocked")}</p>;',
    "接口未提供": 'export const I = () => <span>{t("deref.unavailable")} {id}</span>;',
    "出处引用": "export const J = ({ c }) => <sup>{c.citation_id}</sup>;",
    "取证属性": "export const K = ({ b }) => <p data-block-id={b.block_id}>x</p>;",
    "注释里提端点": "// 服务端那道走 POST /workbenches/{id}/edges\nexport const L = () => <p>x</p>;",
}


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    node = shutil.which("node")
    assert node is not None, "找不到 node：这条门量不了，NEVER 当它通过"
    return subprocess.run([node, str(TOOL), *args], cwd=REPO, capture_output=True,
                          text=True, encoding="utf-8", check=False)


def _dir(tmp_path: Path, name: str, source: str) -> str:
    d = tmp_path / name
    d.mkdir()
    (d / "X.tsx").write_text(source, encoding="utf-8")
    return str(d)


# ───────────────────────── ① 全仓干净


def test_the_product_surface_has_no_scaffolding() -> None:
    """`web/` 的产品面零脚手架。"""
    done = _run("web")

    assert done.returncode == 0, done.stdout + done.stderr


def test_the_scan_actually_reads_files() -> None:
    """扫描面自证：真读到了文件。

    扫 0 个文件也会「零命中」——那种绿与「干净」长得一模一样（F-08 的形状）。
    """
    report = _run("web", "--json").stdout

    import json

    data = json.loads(report)
    assert data["scanned_files"] > 40, f"只扫到 {data['scanned_files']} 个文件，扫描面塌了"


# ───────────────────────── ② 六种脚手架逐条必红


def test_every_scaffolding_shape_is_caught(tmp_path: Path) -> None:
    """六种形态逐条构造，每一条都必须红并点名文件与行号。"""
    for label, source in SCAFFOLD_CASES.items():
        done = _run(_dir(tmp_path, f"bad-{abs(hash(label))}", source))

        assert done.returncode == 1, f"{label} 没被抓住"
        assert "X.tsx" in done.stdout + done.stderr, f"{label} 没点名文件"


# ───────────────────────── ③ 诚实态一条都不许误伤


def test_no_honest_signal_is_mistaken_for_scaffolding(tmp_path: Path) -> None:
    """六种诚实态逐条构造，尺子必须放行。

    这一组比命中组更要紧：一把会误伤诚实态的尺子，会逼着后人把
    「这块被阻断导出」「这个数字有出处」从界面上删掉——**那正好是这套系统最不该丢的东西**。
    """
    for label, source in HONEST_CASES.items():
        done = _run(_dir(tmp_path, f"ok-{abs(hash(label))}", source))

        assert done.returncode == 0, (
            f"误伤了诚实态「{label}」：\n{done.stdout}\n{done.stderr}"
        )


# ───────────────────────── ④ 例外显式登记，NEVER 悄悄放行


def test_the_profile_field_path_exception_is_declared_with_a_reason() -> None:
    """`field_path` 是**登记过的例外**，不是尺子看漏了。

    它是 ProfileRef 出处通道——说的是这个数字来自档案里的哪一项。删了就是删出处
    （acceptance④「诚实态相关的可见信息一条不删」）。但它确实长得像 schema 字段名，
    所以必须**在尺子里写明为什么放行**，而不是让规则悄悄漏过去。
    """
    source = TOOL.read_text(encoding="utf-8")

    assert "field_path" in source
    assert "ProfileRef" in source, "例外没有写明理由"


def test_an_undeclared_field_name_render_is_still_caught(tmp_path: Path) -> None:
    """例外只对 `field_path` 一个：别的 schema 字段名照样红。

    否则「登记例外」就变成了一个谁都能钻的口子。
    """
    done = _run(_dir(tmp_path, "other-field", "export const M = ({ x }) => <p>{x.block_id}</p>;"))

    assert done.returncode == 1
