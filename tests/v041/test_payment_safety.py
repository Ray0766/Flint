"""PAY-03：支付四条安全边界做成机器可验（DEC-024）。

## 四条边界

| # | 边界 | 谁守 |
|---|---|---|
| ① | 仓库 / 日志 / trace 里**零支付密钥** | `tools/check_payment_safety.py` 扫描器 |
| ② | 回调 **MUST 验签**，未验签的处理路径即红 | 同上 |
| ③ | 扣费 **MUST 带幂等键**，同一笔重放只扣一次 | 构造用例（真跑账本） |
| ④ | 代码里**零卡号字段** | 扫描器 |

## 每条都配阴性对照

只断言「全仓干净」是不够的——**一把扫 0 个文件的扫描器也会报干净**，
那种绿与「真的干净」长得一模一样（F-08 的形态）。
所以每条边界都构造一个违规样例，断言扫描器**真的报红**，并点名到文件与行。

## 扫描器接进全局门

尺子已经有了不等于它被跑（F-11 的全部内容）。本文件把扫描器 `subprocess` 起来断 exit 0，
于是 `pytest -q` 从此覆盖它——**NEVER 建一把不在门里的尺子**。

## 本卡不接真实网关

真实商户密钥启用属事前必审（工单 §六.5 红线）。本卡只造尺子与判据。
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

TOOL = REPO / "tools" / "check_payment_safety.py"

# 命中组：每一条都是真会出事的形态。
VIOLATIONS = {
    "微信 APIv3 密钥": 'WECHAT_APIV3_KEY = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"\n',
    "PayPal client_secret": 'client_secret = "EFtBnDoJ7qF3xK9pLmNvQwXyZaBcDeFgHiJkLmNo"\n',
    "私钥块": "KEY = '''-----BEGIN RSA PRIVATE KEY-----\nMIIEow==\n-----END RSA PRIVATE KEY-----'''\n",
    "卡号字段": "class Card:\n    card_number: str\n",
    "CVV 字段": "class Card:\n    cvv: str\n",
    "未验签的回调": (
        "async def wechat_notify(request):\n"
        "    body = await request.json()\n"
        "    return credit(body['out_trade_no'])\n"
    ),
}

# 不误伤组：每一条都是**正常代码**，扫描器放行才算对。
#
# 三条样例的长度与形状是**有意的**：占位符要够长（≥16 字符）才会走到「这是占位符」
# 那一支，注释样例要写成「注释掉的真赋值」才会走到剥注释那一支。
# 不够长/不够像的样例证明不了那两支还活着——变异考⑤⑥ 实测就是这么活下来的。
INNOCENT = {
    "只读环境变量": 'KEY = os.environ.get("FLINT_WECHAT_APIV3_KEY")\n',
    "示例占位": 'WECHAT_APIV3_KEY = "<your-wechat-apiv3-key-goes-here>"\n',
    "注释掉的真赋值": (
        '# client_secret = "EFtBnDoJ7qF3xK9pLmNvQwXyZaBcDeFgHiJkLmNo"\n'
        "KEY = None\n"
    ),
    "验了签的回调": (
        "async def wechat_notify(request):\n"
        "    verify_signature(request.headers, await request.body())\n"
        "    body = await request.json()\n"
        "    return credit(body['out_trade_no'])\n"
    ),
    "叫 card 但不是卡号": "class EvidenceCard:\n    card_id: str\n",
    "文档里写 cvv 三个字母": "# 我们 NEVER 存 cvv\nX = 1\n",
}


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(TOOL), *args], cwd=REPO,
                          capture_output=True, text=True, encoding="utf-8", check=False)


def _tree(tmp_path: Path, name: str, source: str) -> str:
    d = tmp_path / name
    d.mkdir()
    (d / "sample.py").write_text(source, encoding="utf-8")
    return str(d)


# ───────────────────────── 一、全仓干净（acceptance①②④）


def test_the_repo_is_clean() -> None:
    """`flint/` + `tools/` + `docs/` 三棵树全部过关。"""
    done = _run("flint", "tools", "docs")

    assert done.returncode == 0, done.stdout + done.stderr


def test_the_scan_actually_read_files() -> None:
    """扫描面自证：真读到了文件。

    扫 0 个文件也会「零命中」——那种绿与「干净」长得一模一样（F-08 的形态）。
    """
    report = json.loads(_run("flint", "tools", "--json").stdout)

    assert report["files_scanned"] > 50, f"只扫到 {report['files_scanned']} 个文件"
    assert report["findings"] == []


# ───────────────────────── 二、阴性对照：违规样例必须报红


def test_every_violation_is_caught(tmp_path: Path) -> None:
    """命中组逐条报红，且**点名到文件与行**——只说「有问题」的话没人知道去哪儿改。"""
    for name, source in VIOLATIONS.items():
        done = _run(_tree(tmp_path, f"bad_{abs(hash(name))}", source), "--json")

        assert done.returncode == 1, f"「{name}」没被扫出来"
        report = json.loads(done.stdout)
        assert report["findings"], f"「{name}」exit 1 却没给出条目"
        first = report["findings"][0]
        assert first["file"].endswith("sample.py")
        assert first["line"] >= 1
        assert first["rule"], f"「{name}」的条目没写是哪条规则"


def test_no_innocent_code_is_hit(tmp_path: Path) -> None:
    """不误伤组逐条放行。

    一把会误伤正常代码的尺子，会逼着后人把它关掉——那时四条边界一条都不剩。
    """
    for name, source in INNOCENT.items():
        done = _run(_tree(tmp_path, f"ok_{abs(hash(name))}", source), "--json")

        assert done.returncode == 0, (
            f"「{name}」被误伤：{done.stdout}")


def test_a_secret_only_in_an_env_var_is_fine(tmp_path: Path) -> None:
    """密钥只从环境变量读是**正解**，扫描器 NEVER 拦它。"""
    done = _run(_tree(tmp_path, "env_ok", 'k = os.environ["FLINT_PAYPAL_SECRET"]\n'))

    assert done.returncode == 0, done.stdout


def test_the_rules_are_named_in_the_report(tmp_path: Path) -> None:
    """四条边界各有各的规则名——混成一条的话，报出来也不知道犯的是哪一条。"""
    seen = set()
    for source in VIOLATIONS.values():
        done = _run(_tree(tmp_path, f"r_{abs(hash(source))}", source), "--json")
        seen |= {f["rule"] for f in json.loads(done.stdout)["findings"]}

    assert {"payment_secret", "card_field", "unverified_callback"} <= seen, seen


# ───────────────────────── 三、回调必须验签（acceptance②）


def test_a_callback_without_verification_is_red(tmp_path: Path) -> None:
    """看起来是支付回调、却没有任何验签调用 → 红。

    不验签的回调等于把「谁都能说这笔付过了」做成了一个端点。
    """
    done = _run(_tree(tmp_path, "cb_bad", VIOLATIONS["未验签的回调"]), "--json")

    assert done.returncode == 1
    rules = {f["rule"] for f in json.loads(done.stdout)["findings"]}
    assert "unverified_callback" in rules


def test_a_callback_with_verification_is_green(tmp_path: Path) -> None:
    done = _run(_tree(tmp_path, "cb_ok", INNOCENT["验了签的回调"]))

    assert done.returncode == 0, done.stdout


def test_verification_in_another_function_does_not_save_the_callback(tmp_path: Path) -> None:
    """验签写在**同文件的别的函数**里救不了这一个回调。

    把判定放宽到整份文件的话，一个真没验签的回调只要文件里别处有 `verify_signature`
    就能蒙混过关——而那个别处的验签根本没跑到这条路径上（变异考⑧ 实测）。
    """
    source = (
        "def some_other_handler(request):\n"
        "    verify_signature(request.headers, request.body)\n"
        "    return 1\n"
        "\n"
        "async def wechat_notify(request):\n"
        "    body = await request.json()\n"
        "    return credit(body['out_trade_no'])\n"
    )
    done = _run(_tree(tmp_path, "cb_elsewhere", source), "--json")

    assert done.returncode == 1, "验签在别的函数里，这个回调却被放行了"
    rules = {f["rule"] for f in json.loads(done.stdout)["findings"]}
    assert "unverified_callback" in rules


def test_the_self_exemption_names_exactly_the_files_that_must_contain_the_shapes() -> None:
    """自豁免**只放行四个具名文件**，NEVER 放大成「跳过 tools/ 与 tests/」。

    放大之后，那两棵树里真出现的密钥就再也扫不到了——
    而扫描器自己看起来照样是绿的（变异考⑬ 实测）。
    """
    from tools.check_payment_safety import SELF_EXEMPT

    assert SELF_EXEMPT == {
        "tools/check_payment_safety.py",
        "tests/v041/test_payment_safety.py",
        "docs/支付接入方案-v041.md",
        "docs/trace/PAY-03.md",
    }
    for rel in SELF_EXEMPT:
        assert "*" not in rel and not rel.endswith("/"), f"豁免项是个目录/通配：{rel}"


def test_a_secret_inside_the_real_tools_tree_is_still_caught() -> None:
    """豁免是**逐文件**的：`tools/` 下别的文件出现密钥照样红。

    这一条必须把探针写进**真的 `tools/`**：写进 tmp 目录的话，它的相对路径不以
    `tools/` 开头，于是「把豁免放大成整棵树」这个改动对它毫无影响——
    判据照样绿（变异考⑬ 实测就是这么活下来的）。

    与 GAUGE-01 的构造用例同一条口径：敢改真目录，因为 `finally` 一定删掉，
    且末尾再断言一次探针确实不在了。
    """
    probe = REPO / "tools" / "_pay_safety_probe_tmp.py"
    assert not probe.exists(), "上一次的探针没删干净"
    try:
        probe.write_text(VIOLATIONS["PayPal client_secret"], encoding="utf-8")
        done = _run("tools", "--json")

        assert done.returncode == 1, "tools/ 下的密钥没被扫出来"
        hits = [f for f in json.loads(done.stdout)["findings"]
                if f["file"].endswith("_pay_safety_probe_tmp.py")]
        assert hits, "扫描器跳过了整棵 tools/"
    finally:
        probe.unlink(missing_ok=True)

    assert not probe.exists()
    assert _run("tools").returncode == 0, "探针删掉之后 tools/ 应当回到干净"


def test_a_function_that_is_not_a_callback_is_not_judged(tmp_path: Path) -> None:
    """只有**看起来是支付回调**的函数才被这条规则管。

    见函数就要验签的话，整棵树都会红——那把尺子会被立刻关掉。
    """
    done = _run(_tree(tmp_path, "plain", "async def load_cards(request):\n    return []\n"))

    assert done.returncode == 0, done.stdout


# ───────────────────────── 四、扣费带幂等键，重放只扣一次（acceptance①③）


def test_a_replayed_charge_lands_only_once() -> None:
    """同一笔重放两次，账上只有一条、金额不翻倍。

    这一条打在**真账本**上，不是打在源码文本上：
    「代码里有 event_id 这个词」与「重放真的扣不了第二次」是两件事。
    """
    from flint.billing.ledger import BillingLedger, LedgerImmutable
    from flint.billing.meter import MeterConfig, charge_event
    from flint.domain.models import Principal
    from flint.llm.deepseek import UsageRecord

    owner = Principal(id="u-1", kind="user")
    usage = [UsageRecord(
        call_id="c-1", model="deepseek-chat", purpose="compose",
        input_tokens=1_000_000, output_tokens=0, cache_hit_tokens=0,
        cache_miss_tokens=1_000_000, cost_usd=Decimal("0.14"),
        pricing_version="deepseek-v4-flash@2026-08")]
    config = MeterConfig(
        price_per_mtok_input=Decimal("2.00"), price_per_mtok_output=Decimal("8.00"),
        currency="USD", pricing_version="flint-billing@2026-08-05")
    at = datetime(2026, 8, 5, 1, 0, 0, tzinfo=UTC)

    ledger = BillingLedger()
    first = charge_event(usage, job_id="job-1", owner=owner, config=config, at=at)
    assert first is not None
    ledger.append(first)

    replay = charge_event(usage, job_id="job-1", owner=owner, config=config, at=at)
    assert replay is not None
    try:
        ledger.append(replay)
    except LedgerImmutable:
        pass
    else:
        raise AssertionError("重放被记了第二条：同一笔扣了两次")

    summary = ledger.reconcile(owner)
    assert summary["count"] == 1
    assert summary["total"] == Decimal("2.00")


def test_the_idempotency_key_is_stable_across_processes() -> None:
    """幂等键要**跨进程稳定**：用 `id()` 或随机数当键的话，重启一次就重复扣了。"""
    from flint.billing.meter import charge_event_id
    from flint.domain.models import Principal

    owner = Principal(id="u-1", kind="user")
    args = {"job_id": "job-1", "owner": owner, "pricing_version": "v1"}

    computed = charge_event_id(**args)  # type: ignore[arg-type]
    snippet = (
        f"import sys; sys.path.insert(0, r'{REPO}');"
        "from flint.billing.meter import charge_event_id;"
        "from flint.domain.models import Principal;"
        "print(charge_event_id(job_id='job-1', owner=Principal(id='u-1', kind='user'),"
        " pricing_version='v1'))"
    )
    other = subprocess.run(
        [sys.executable, "-c", snippet],
        capture_output=True, text=True, encoding="utf-8", check=True)

    assert other.stdout.strip() == computed, "幂等键跨进程不稳定"


def test_two_different_jobs_are_not_deduplicated() -> None:
    """反向：不同作业 NEVER 被当成同一笔。

    见谁都当重放的幂等键会把两笔真实消费吞掉一笔。
    """
    from flint.billing.meter import charge_event_id
    from flint.domain.models import Principal

    owner = Principal(id="u-1", kind="user")

    assert charge_event_id(job_id="a", owner=owner, pricing_version="v1") != \
        charge_event_id(job_id="b", owner=owner, pricing_version="v1")


def test_two_owners_never_share_a_charge_key() -> None:
    """不同 owner 的同名作业 NEVER 撞键（D7 多租户）。"""
    from flint.billing.meter import charge_event_id
    from flint.domain.models import Principal

    assert charge_event_id(
        job_id="a", owner=Principal(id="u-1", kind="user"), pricing_version="v1"
    ) != charge_event_id(
        job_id="a", owner=Principal(id="u-2", kind="user"), pricing_version="v1")


# ───────────────────────── 五、扫描器在门里（acceptance③）


def test_the_scanner_is_started_from_inside_the_test_suite() -> None:
    """尺子已经有了不等于它被跑（F-11 的全部内容）。

    本文件用 `subprocess` 起它并断 exit 0——于是 `pytest -q` 从此覆盖它。
    这条判据自证：本文件里真的有起它的代码。
    """
    source = Path(__file__).read_text(encoding="utf-8")

    assert "check_payment_safety.py" in source
    assert "_run(" in source


def test_the_tool_refuses_to_report_clean_on_an_empty_target(tmp_path: Path) -> None:
    """扫不到任何文件时**报红**，NEVER 报干净。

    路径写错、目录空了、glob 没匹配上——三种情况都长得像「干净」。
    """
    empty = tmp_path / "nothing"
    empty.mkdir()
    done = _run(str(empty))

    assert done.returncode != 0, "扫 0 个文件却报了干净"
    assert "0 个文件" in done.stdout + done.stderr


def test_the_tool_is_not_wired_to_any_gateway() -> None:
    """本卡不接真实网关：扫描器自己 NEVER 发请求、NEVER 读环境里的真密钥。

    判在 **AST** 上，不判「正文里出现了这个词」——后者会被模块 docstring 里
    那句「`os.environ[...]` 放行」喂饱（实测红过一次）。
    **解释规则的话与执行规则的代码是两回事**，这是本轮第六次撞上同一形状。
    """
    import ast

    tree = ast.parse(TOOL.read_text(encoding="utf-8"))

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert not ({"httpx", "requests", "urllib", "socket"} & imported), imported

    reads_env = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Attribute) and n.attr == "environ"
    ]
    assert reads_env == [], "扫描器去读环境变量了：读了就等于多一份泄露面"
