"""DSN-ISO：tests/ 里 NEVER 出现「无 env 兜底的真 DSN 字面量」。

根因回归（已咬六次）：演示库与测试库共用一个 PG——跑一次 `pytest -q`，demo 的
projects / topics / deliverables / snapshots 就被各测试的 wipe fixture 清空。
治本是分库（flint_test），但只要还有**一处** DSN 写死不读 env，分库就被那一处绕过去。
本测试守的就是这条缝：它不测业务，测的是「连哪个库」这件事没有后门。

## 判「真 DSN」的口径（NEVER 用会误伤假 DSN 的粗正则）

只认**指向本机 compose PG 端口 55432** 的连接串：
    postgresql[+driver]://user:pw@host:55432/dbname
compose.yaml 把 PG 映射到 55432，测试套件真正连的只有这个端口。于是：

- `"postgresql://unused"`（tests/m3/* 给 build_offline_deps 的假 DSN）——无 `@`、无端口，
  离线 deps 从不连库 → 天然排除，NEVER 误伤。
- `"postgresql://x"`（tests/m4/test_m4_039.py）——同上 → 排除。
- `"postgresql+asyncpg://flint:flint@localhost:5432/flint"`（tests/m1/test_m1_005.py）——
  端口 **5432**，是 Settings 解析用的**配置夹具值**，从不开 socket → 排除。

## 判「有 env 兜底」

该字面量必须是 `os.environ.get(...)` / `os.getenv(...)` 的**第二个实参**——按 AST 结点
身份（`id()`）比对，NEVER 靠行文本猜（跨行写法 tests/m1/test_m1_003.py 也要认得出）。
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

TESTS_ROOT = Path(__file__).resolve().parents[1]

# 本机 compose PG 端口（compose.yaml: "55432:5432"）——只有连它的串才算「真 DSN」。
COMPOSE_PG_PORT = "55432"
_REAL_DSN = re.compile(
    r"^postgresql(\+[a-z0-9]+)?://[^\s/@]+@[^\s/:]+:" + COMPOSE_PG_PORT + r"/\w+"
)
# 测试侧统一的注入口（54 处既有写法即此名）。
TEST_DSN_ENV = "FLINT_TEST_DSN"
# 分库后测试只许连这个库；demo 库叫 flint，NEVER 出现在测试默认值里。
TEST_DB_NAME = "flint_test"
DEMO_DB_NAME = "flint"


def _is_env_lookup(func: ast.expr) -> bool:
    """匹配 os.environ.get / environ.get / os.getenv / getenv。"""
    if not isinstance(func, ast.Attribute):
        return False
    if func.attr == "getenv":
        return True
    if func.attr != "get":
        return False
    value = func.value
    if isinstance(value, ast.Name):
        return value.id == "environ"
    return isinstance(value, ast.Attribute) and value.attr == "environ"


def _test_files() -> list[Path]:
    return sorted(p for p in TESTS_ROOT.rglob("*.py") if "__pycache__" not in p.parts)


def _scan(path: Path) -> tuple[list[int], list[tuple[int, str, str]]]:
    """返回（无 env 兜底的真 DSN 行号, [(行号, env 变量名, DSN 值)] 有兜底的）。

    DSN 值直接取自 AST 结点，NEVER 回头再去解析行文本——行文本里 DSN 不在行首，
    而 _REAL_DSN 是 `^` 锚定的，那样取会稳定取空。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    guarded: dict[int, str] = {}          # id(结点) -> env 变量名
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and _is_env_lookup(node.func)
            and len(node.args) == 2
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            guarded[id(node.args[1])] = node.args[0].value

    bare: list[int] = []
    covered: list[tuple[int, str, str]] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        if not _REAL_DSN.match(node.value):
            continue
        env_name = guarded.get(id(node))
        if env_name is None:
            bare.append(node.lineno)
        else:
            covered.append((node.lineno, env_name, node.value))
    return bare, covered


def test_no_hardcoded_dsn_without_env_fallback() -> None:
    """tests/ 下每一个真 DSN 字面量都必须是 env 的兜底默认值。"""
    offenders = []
    for path in _test_files():
        bare, _ = _scan(path)
        offenders += [f"{path.relative_to(TESTS_ROOT.parent)}:{line}" for line in bare]
    assert offenders == [], (
        "以下位置把真 DSN 写死、没有 env 兜底——分库后它们会绕过 FLINT_TEST_DSN "
        "直接连上写死的库：\n  " + "\n  ".join(offenders)
    )


def test_every_dsn_default_is_keyed_by_test_dsn_env() -> None:
    """测试侧的注入口统一是 FLINT_TEST_DSN（NEVER 混入 demo 库的 env 名）。"""
    wrong = []
    for path in _test_files():
        _, covered = _scan(path)
        wrong += [
            f"{path.relative_to(TESTS_ROOT.parent)}:{line} 用的是 {env}"
            for line, env, _dsn in covered
            if env != TEST_DSN_ENV
        ]
    assert wrong == [], (
        f"测试里的真 DSN 只能由 {TEST_DSN_ENV} 注入：\n  " + "\n  ".join(wrong)
    )


def test_every_dsn_default_points_at_the_test_database() -> None:
    """默认值指向 flint_test —— 这条才是真正把 demo 库摘出去的断言。

    上面两条只保证「能被 env 改」；只要默认值仍是 demo 库，不设 env 的那次 `pytest -q`
    照样把 demo 数据清空。默认值必须自洽：**不设任何环境变量也连测试库**。
    """
    wrong = []
    for path in _test_files():
        _, covered = _scan(path)
        for line, _env, dsn in covered:
            db = dsn.rsplit("/", 1)[1]
            if db != TEST_DB_NAME:
                rel = path.relative_to(TESTS_ROOT.parent)
                extra = "（这是 demo 库）" if db == DEMO_DB_NAME else ""
                wrong.append(f"{rel}:{line} 默认库是 {db}{extra}")
    assert wrong == [], (
        f"测试的默认 DSN 必须指向 {TEST_DB_NAME}：\n  " + "\n  ".join(wrong)
    )


def _database_name(dsn: str) -> str:
    return dsn.rsplit("/", 1)[-1].split("?", 1)[0]


_WRITE_SQL = re.compile(r"\b(INSERT|UPDATE|DELETE|TRUNCATE|CREATE|DROP|ALTER)\b", re.IGNORECASE)
_WRITE_CALLS = {"execute", "executemany", "copy_records_to_table"}


def _db_writes(path: Path) -> list[str]:
    """模块里的写库动作（写 SQL 字面量 + execute 类调用）。

    只看 AST，NEVER 扫注释——注释里写着 INSERT/UPDATE 这些词不构成写操作，
    扫注释会把说明文字当成罪证（本文件的注释里就有这些词）。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and _WRITE_SQL.search(node.value)
        ):
            found.append(f"{path.name}:{node.lineno} 写 SQL 字面量")
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in _WRITE_CALLS
        ):
            found.append(f"{path.name}:{node.lineno} 调用 {node.func.attr}")
    return found


def test_gate1_live_writes_to_the_test_database_when_imported() -> None:
    """harness.gate1_live 是双身份模块——判断错就等于没修。

    它 `_wipe` 删 jobs/job_steps/job_events/snapshots 再写回，是真会写库的：
      · tests/m2/test_featb_gate1_live.py 导入它 → 必须落测试库；
      · 人手动 `python -m harness.gate1_live replay-qwen` → 才该落 demo 库（恢复判定样本）。
    本断言只钉「导入路径」这一侧——CLI 那一侧在 __main__ 里显式改写 DSN，
    模块常量必须保持指向测试库。
    """
    from harness import gate1_live

    assert _database_name(gate1_live.DSN) == TEST_DB_NAME, (
        f"gate1_live 被导入时会写 {gate1_live.DSN}——测试会污染 demo 库")
    assert _database_name(gate1_live.DEMO_DSN) == DEMO_DB_NAME, (
        "CLI 路径要能把样本恢复进 demo 库，DEMO_DSN 必须仍指 demo")


def test_topic_caliber_stays_read_only() -> None:
    """topic_caliber 连 demo 库的前提是它**只读**——这条前提得由测试守着。

    它读 demo 库不是习惯，是数据：回放用例要按 asset 里的真实 card_ids 还原 seed，
    那些卡只在 demo 库里。只读就污染不了。哪天有人给它加了写操作，这条断言会红，
    逼着重新决定它该连哪个库，而不是让污染悄悄发生。
    注：只扫 AST（字符串常量 + 调用名），NEVER 扫注释——注释里写着 INSERT/UPDATE
    这些词本身不构成写操作，扫注释会把说明文字当成罪证。
    """
    harness_dir = TESTS_ROOT.parent / "harness"
    assert _db_writes(harness_dir / "topic_caliber.py") == [], (
        "topic_caliber 出现了写库动作，它却连着 demo 库："
        f"\n  {_db_writes(harness_dir / 'topic_caliber.py')}"
    )
    # 阳性对照：同一个探测器打到真会写库的 gate1_live 上必须有命中。
    # 否则「topic_caliber 没有写操作」这个结论可能只是探测器什么都测不出来。
    assert _db_writes(harness_dir / "gate1_live.py") != [], "探测器空转：连 gate1_live 的写都测不出来"


def test_scanner_excludes_deliberate_fake_dsns() -> None:
    """反向自证：故意的假 DSN 与配置夹具值 NEVER 被这个扫描器误伤。

    扫描器自己要是把 postgresql://unused 判成真 DSN，上面两条断言就会逼着别人去
    「修」一个本来就对的地方——那比不扫更糟。
    """
    for fake in ("postgresql://unused", "postgresql://x",
                 "postgresql+asyncpg://flint:flint@localhost:5432/flint"):
        assert not _REAL_DSN.match(fake), f"扫描器误伤了假 DSN：{fake}"
    # 正向：真 DSN 必须被认出来（否则上面两条断言全绿等于空转）。
    # 样本用拼接构造而**不写成字面量**——否则本文件自己就成了扫描器的第 12 个命中，
    # 而给本文件开豁免等于在扫描器上留一个后门。拼接的每一段都不匹配整串规则。
    host = "flint:flint@localhost:" + COMPOSE_PG_PORT
    for real in ("postgresql://" + host + "/flint",
                 "postgresql://" + host + "/flint_test",
                 "postgresql+asyncpg://flint:flint@127.0.0.1:" + COMPOSE_PG_PORT + "/flint"):
        assert _REAL_DSN.match(real), f"扫描器漏掉了真 DSN：{real}"
