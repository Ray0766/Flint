"""STALE-01：热点卡的陈旧槽恒不显示，**而本卡的产品是那条禁令**（`DEC-039`）。

## 隐藏一个槽不需要一张卡

`clusterToCard` 本来就没传 `stale`，`HotspotCard` 本来就只在 `=== true` 时才渲染。
**槽今天已经是隐藏的**——把这件事再做一遍，产出为零。

真正值钱的是挡住下一个人：`clusters.last_active` 就在手边，
拿它跟今天一比就能算出「多少天没动了」，那一版看起来**更完整**，
而它说的每一句都是假的——

> 热点簇不是一份分析：它不引用事实，**它是事实的来源之一**。

`Revalidator` 判的是「一份分析引用过的事实变没变」，要 `project_id`、账本版本、
被引用的那些事实三样，而 `clusters` 表一样都没有。拿时间戳顶上去，
**是新写一套比对**（`SLOT-02` acceptance① 明令禁止），**而且它说的是系统不知道的事**。

## 禁的是「据此置陈旧」，不是「时间戳算术」

这条边界是本卡最要紧的一句。库里今天有三处正当的时间戳算术：

| 出处 | 算什么 | 为什么正当 |
|---|---|---|
| `flint/signals.py:33` | `novelty`：`first_seen` 距今 ≤ 7 天 | 新颖度，规格 `#3.3` 的信号 |
| `flint/lineage/s4.py:29` | `dormant`：`last_active` 距今 ≥ N 天 | **沉寂**，血缘状态机 S4 |
| `flint/hotness.py:78` | `age_days`：热度衰减的年龄项 | 衰减曲线的自变量 |

三处都不叫「陈旧」。这正是 `SLOT-02` 单里那句话的机器形态——
**「沉寂」是个有用的东西，但它不叫「陈旧」**；把它们一起禁掉的尺子会当场废掉三个正确实现，
而那种尺子会在第一次误报后被人整条注释掉。

所以规则是**两个条件同时成立**才算违规：
① 表达式里有 `last_active` / `first_seen` 参与的算术或比较；
② 这个表达式被绑到一个**陈旧词**上（赋值目标 / 字典键 / 关键字参数 / 函数名）。

## 判据 NEVER 把说明问题的那句话当成问题本身

`flint/fav/stale.py` 的 docstring 逐字写着「更 NEVER 按时间戳推断新鲜度」，
`StaleNotEvaluated` 抛出的中文里带着「不陈旧」——**它们是禁令的解释，不是违规**。
本仓已经七次栽在这同一个形状上（规格 `#2.4` · `backfill.py` · 噪声基线 ·
`check_fe_be_parity` 的旧白名单 · `FIX-12` 的枚举扫描 · `test_endpoint_triage` 的读缓存判据 ·
`GAUGE-14` 的首段清单）。

尺子这次从一开始就走 AST：Python 侧只看**真的把表达式绑到陈旧名上**的那种节点，
docstring 与异常消息是 `Expr`/`Call`，天然不在其列；TS 侧先剥注释再判。
下面 `test_the_ruler_does_not_flag_prose_that_explains_the_ban` 把这件事钉死。
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

TOOL = REPO / "tools" / "check_no_timestamp_staleness.py"
CARD = REPO / "web" / "components" / "hotspot-card" / "HotspotCard.tsx"
MAPPER = REPO / "web" / "components" / "plaza" / "clusterToCard.ts"
FAV_STALE = REPO / "flint" / "fav" / "stale.py"
ADAPTER = REPO / "flint" / "analysis" / "stale_adapter.py"
SHEET = (REPO / "docs" / "blocked"
         / "SLOT-02-A-CLUSTER-HAS-NOTHING-THE-REVALIDATOR-CAN-JUDGE.md")


def _scan(root: Path) -> list[str]:
    from tools.check_no_timestamp_staleness import scan_tree

    return [str(v) for v in scan_tree(root)]


# ───────────────────────── 一、acceptance②：本仓今天是干净的


def test_the_repo_has_no_timestamp_derived_staleness() -> None:
    """全仓扫描：一处「据时间戳置陈旧」都没有。

    这是本卡的**正面事实**。它单独一条不够——一把什么都不报的尺子也能让它绿，
    所以下面每一条阴性对照都在证明它不是空转。
    """
    violations = _scan(REPO)

    assert violations == [], "全仓出现了据时间戳推断的陈旧：\n" + "\n".join(violations)


def test_the_ruler_runs_clean_as_a_command() -> None:
    """尺子能当命令跑，退出码 0——它要能进全局门，不只是被测试 import。"""
    done = subprocess.run(
        [sys.executable, str(TOOL)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=REPO, timeout=300, check=False)

    assert done.returncode == 0, done.stdout[-3000:] + done.stderr[-3000:]


# ───────────────────────── 二、acceptance③：阴性对照，且点名文件与行


def _write(root: Path, rel: str, body: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def test_a_python_timestamp_shortcut_is_caught_with_file_and_line() -> None:
    """**本卡的核心阴性对照**：往任一模块插一处时间戳减法并据此置 stale。

    只断言「报了红」不够——报告 MUST 点名**文件与行**，
    否则读到红的人还要自己去全仓找那一行，而那正是他会放弃的地方。
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write(root, "flint/plaza/shortcut.py",
               "from datetime import date\n"
               "\n"
               "def build(cluster, today: date) -> dict:\n"
               "    stale = (today - cluster.last_active).days > 7\n"
               "    return {'stale': stale}\n")

        found = _scan(root)

    assert len(found) == 1, f"没抓到，或抓重了：{found}"
    assert "shortcut.py" in found[0], f"没点名文件：{found[0]}"
    assert ":4:" in found[0], f"没点名行号（应为第 4 行）：{found[0]}"
    assert "last_active" in found[0], f"没写清是哪个字段：{found[0]}"


def test_a_shortcut_hidden_in_a_dict_literal_is_caught() -> None:
    """写法二：不落地成变量，直接塞进返回的字典。

    只认 `x = ...` 的话，`return {"stale": now - t > N}` 一行就绕过去了。
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write(root, "flint/api/plaza.py",
               "from datetime import date\n"
               "\n"
               "def row(c, today: date) -> dict:\n"
               "    return {\n"
               "        'cluster_id': c.cluster_id,\n"
               "        'stale': (today - c.last_active).days >= 30,\n"
               "    }\n")

        found = _scan(root)

    assert len(found) == 1, f"字典键那种写法没抓到：{found}"
    assert ":6:" in found[0], found[0]


def test_a_shortcut_in_a_typescript_file_is_caught() -> None:
    """写法三：搬到前端去算。

    规格 `#2.15` 与冻结件 `Favorite` 的 docstring 都点名禁的是**前端自行推断**，
    所以尺子 NEVER 只扫 Python——只扫一边的话，这条捷径会挪到另一边。
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write(root, "web/components/plaza/cardStale.ts",
               "export function toCard(c: Cluster) {\n"
               "  const stale = Date.now() - Date.parse(c.last_active) > 7 * 864e5;\n"
               "  return { ...c, stale };\n"
               "}\n")

        found = _scan(root)

    assert len(found) == 1, f"TS 那边没抓到：{found}"
    assert ":2:" in found[0], found[0]


def test_the_camel_case_spelling_is_caught_too() -> None:
    """前端把字段名驼峰化之后仍然是同一件事。

    `firstSeen` / `lastActive` 是 `clusterToCard` 那一层的命名法——
    只认下划线的话，这条捷径过一次搬运就隐身了。
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write(root, "web/lib/staleness.ts",
               "export const isOutdated = (card: Card) =>\n"
               "  Date.now() - new Date(card.lastActive).getTime() > 6048e5;\n")

        found = _scan(root)

    assert found, "驼峰写法漏了"
    assert "lastActive" in found[0], found[0]


# ───────────────────────── 三、精度：正当的时间戳算术 NEVER 被误伤


def test_novelty_and_dormancy_and_decay_are_not_flagged() -> None:
    """**反向守卫**：库里三处正当的时间戳算术照旧过。

    一把把它们也报红的尺子会当场废掉三个正确实现，
    而那种尺子会在第一次误报之后被人整条注释掉——**那时它一条都不再守**。

    这三处也顺带证明上面那条「全仓干净」不是因为尺子什么都不看：
    它看得见这些表达式，只是判定它们不叫「陈旧」。
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write(root, "flint/signals.py",
               "def novelty(today, first_seen, days: int) -> bool:\n"
               "    return (today - first_seen).days <= days\n")
        _write(root, "flint/lineage/s4.py",
               "def dormant(today, last_active, after: int) -> bool:\n"
               "    return (today - last_active).days >= after\n")
        _write(root, "flint/hotness.py",
               "def age(today, first_seen) -> int:\n"
               "    age_days = max(0, (today - first_seen).days)\n"
               "    return age_days\n")

        found = _scan(root)

    assert found == [], f"正当的时间戳算术被误伤了：{found}"


def test_the_ruler_does_not_flag_prose_that_explains_the_ban() -> None:
    """**判据 NEVER 把说明问题的那句话当成问题本身**（本仓第八次撞见同一形状）。

    docstring 里逐字写着禁令、异常消息里带着「不陈旧」、TS 注释里写着示例——
    三样都是**禁令的解释**。把它们判成违规的话，写清楚这条禁令的人会被自己的尺子罚。
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write(root, "flint/fav/stale.py",
               '"""更 NEVER 按时间戳推断新鲜度：stale = now - last_active > 7 天。"""\n'
               "\n"
               "\n"
               "class StaleNotEvaluated(Exception):\n"
               "    def __init__(self) -> None:\n"
               "        super().__init__('NEVER 悄悄标成不陈旧')\n")
        _write(root, "web/lib/notes.ts",
               "// 反例：const stale = Date.now() - c.lastActive > N —— NEVER 这么写\n"
               "/* 也不许 stale = firstSeen < cutoff */\n"
               "export const nothing = 1;\n")

        found = _scan(root)

    assert found == [], f"解释禁令的话被当成了违规：{found}"


# ───────────────────────── 四、acceptance④：`snapshot_stale` 的语义一字不动


def test_the_favorite_snapshot_stale_semantics_are_untouched() -> None:
    """`Favorite.snapshot_stale` 说的是「**你收藏的那份快照旧了**」。

    NEVER 被借去说「这个热点旧了」——两句话不是一回事（`DEC-038` 同一形状）：
    前者是我这份存档过时了，后者是这个热点不再活跃。
    """
    from contracts_v04.models_v04 import Favorite

    assert "snapshot_stale" in Favorite.__dataclass_fields__
    assert Favorite.__dataclass_fields__["snapshot_stale"].type in (
        "bool", bool), "字段类型被动过"

    body = FAV_STALE.read_text(encoding="utf-8")
    assert "analysis_stale" in body, "收藏那条 stale 不再走统一口径的适配器了"
    assert ADAPTER.exists()


def test_the_plaza_never_borrows_the_favorite_mark() -> None:
    """广场 NEVER 借收藏那个记号——它今天也借不到，而「借不到」不是判据。

    `fav/store.py:35` 自述是内存实现、`favorites` 表不存在、广场是匿名屏没有身份头：
    三件事任何一件被修好，这条捷径就通了。**所以判据钉的是「不借」本身。**
    """
    mapper = MAPPER.read_text(encoding="utf-8")
    code = "\n".join(
        line for line in mapper.splitlines() if not line.lstrip().startswith("//"))

    assert "stale" not in code, "广场的搬运层开始传 stale 了"
    assert "snapshot_stale" not in code
    assert "favorite" not in code.lower(), "广场的搬运层引到了收藏那一族"


# ───────────────────────── 五、acceptance⑤：槽位保留 + 恢复条件写在一处


def test_the_slot_is_kept_and_says_how_to_restore_it() -> None:
    """槽**保留**（哪天真有可判的东西，改这一处即可），而不是删掉。

    删掉的话，恢复它的人要重新决定挂在哪一格、用什么记号、什么文案——
    那些当初都是照素材定过的。**留着槽 + 写清恢复条件，比删掉便宜得多。**
    """
    card = CARD.read_text(encoding="utf-8")

    assert "data-testid=\"hotspot-stale\"" in card, "槽被删了"
    assert "stale === true" in card, "挂标记的条件不再是恒等于 true"
    assert "DEC-039" in card, "卡面没写这一槽为什么恒不显示"
    assert "恢复条件" in card, "没写清哪天怎么把它打开"


def test_the_mark_still_requires_an_exact_true() -> None:
    """挂标记的条件恒是 `=== true`。

    写成 `{stale && …}` 时行为一样，但下一个人改成 `{stale !== false && …}`
    不会有任何判据响——**而那一版会给「没判过」的簇挂上陈旧标记**。
    """
    card = CARD.read_text(encoding="utf-8")

    assert "stale !== false" not in card
    assert "{stale &&" not in card


# ───────────────────────── 六、acceptance⑥：单据关掉


def test_the_sheet_is_closed_and_records_which_option_won() -> None:
    """单子关掉，并写明 owner 挑的是哪一个——**只写「已解决」的话，四选一就没留下答案**。"""
    text = SHEET.read_text(encoding="utf-8")
    head = "\n".join(text.splitlines()[:8])

    assert "**状态** closed" in head, f"单据还开着：{head!r}"
    assert "DEC-039" in text
    assert "甲" in text, "没写清 owner 挑的是哪一项"
    assert "STALE-01" in text, "没写清是被哪张卡关掉的"
