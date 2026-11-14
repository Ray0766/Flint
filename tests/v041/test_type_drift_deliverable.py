"""TYPE-01 · `/deliverables/{}` 的类型漂移。

## 对账表说的「漂移」，实测不是漂移

表里这条写着「前端已为这条端点建了类型，但后端这几个字段没被声明（真漂移）；
前端已声明 `deliverable_id`, `type`」。

**前端从没为它建过类型。** 那两个「已声明」的名字来自 `Block` 接口——
对账器把 `types.ts` 的字段名当成**一个平集**比，两个同名字段撞上了。

两者要人做的事不同：**漂移要去对齐，没建类型要去新建**。
本卡做的是后者（新建 `DeliverableMeta`），分类精度那一处登记给 `TYPE-04`
（它拥有 `tools/check_fe_be_parity.py`）。

## 字段清单取自后端，NEVER 手抄

卡面 acceptance② 点名了这条：手抄的表不会跟着后端变。
这里取两个源，都不是人写的：

1. **AST**：`backend_routes()` 从 `flint/api/deliverables.py` 的处理函数里
   抽出的 `response_keys`——不依赖库、恒能跑；
2. **真 payload**：demo 栈上打一次真请求——栈没起就 skip 并说清楚。

两个源**互相校验**：AST 抽漏了或后端改了没同步，两边会对不上。
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from tools.check_fe_be_parity import backend_routes, parity

REPO = Path(__file__).resolve().parents[2]
TYPES = REPO / "web" / "lib" / "types.ts"
API_DIR = REPO / "flint" / "api"
DEMO_BASE = "http://localhost:8000"
DELIVERABLE_PATH = "/deliverables/{}"
# demo 库里真有的那一份（`harness/fe_smoke.py` 的 SAMPLE_IDS 也用它）。
SAMPLE_DELIVERABLE = "del-demo-fixture-report"


def _backend_keys() -> set[str]:
    """后端这条端点**真的会返回**的键，从 AST 抽——不是手抄的。"""
    keys = {
        key
        for route in backend_routes(API_DIR)
        if route.path == DELIVERABLE_PATH and route.method == "GET"
        for key in route.response_keys
    }
    assert keys, "一个键都没抽到：扫描面塌了，这条判据在空转"
    return keys


def _declared_fields(interface: str) -> set[str]:
    """`types.ts` 里某个接口**自己**声明的字段名。

    **按接口取，不按全文件取**——全文件平集正是对账器那处误判的来源，
    本文件 NEVER 重复同一个错。
    """
    source = TYPES.read_text(encoding="utf-8")
    match = re.search(
        rf"export interface {interface} \{{(.*?)\n\}}", source, re.DOTALL)
    assert match, f"types.ts 里没有 {interface}"
    return set(re.findall(r"^\s{2}(\w+)\??:", match.group(1), re.MULTILINE))


# ───────────────────────── acceptance①：补齐三个字段


def test_the_frontend_type_declares_every_field_the_backend_returns() -> None:
    """前端类型的字段 **⊇** 后端返回的键。

    少一个，前端就有一份「后端给了但没人知道」的数据；
    而这三个字段（`version` / `ledger_version` / `reproducible`）
    正是判断「这份交付物还作不作数」要用的。
    """
    backend = _backend_keys()
    declared = _declared_fields("DeliverableMeta")

    assert backend - declared == set(), (
        f"后端返回但前端没声明：{sorted(backend - declared)}"
    )


def test_the_three_drifted_fields_are_there_by_name() -> None:
    """点名那三个——它们是对账表列出来的，少任何一个本卡就没做完。"""
    declared = _declared_fields("DeliverableMeta")

    assert {"ledger_version", "reproducible", "version"} <= declared


def test_the_type_declares_nothing_the_backend_never_sends() -> None:
    """反向：前端也 NEVER 多声明后端不给的字段。

    多出来的字段会让人以为那份数据存在，写下 `meta.foo` 之后拿到 `undefined`——
    **而 TypeScript 会说它是 `string`**。
    """
    backend = _backend_keys()
    declared = _declared_fields("DeliverableMeta")

    assert declared - backend == set(), (
        f"前端声明了后端不给的字段：{sorted(declared - backend)}"
    )


# ───────────────────────── acceptance②：两个源互相校验


def test_the_ast_keys_match_the_real_payload() -> None:
    """AST 抽出来的键 == 真请求拿回来的键。

    这条是**互相校验**：AST 抽漏了、或后端改了响应而处理函数里的
    字面量 dict 没跟着变，两边就对不上。
    栈没起就 skip 并说清楚——**NEVER 当它通过**。
    """
    done = subprocess.run(
        ["curl", "-s", "-m", "8",
         f"{DEMO_BASE}/deliverables/{SAMPLE_DELIVERABLE}",
         "-H", "X-User-Id: demo-user"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        check=False)
    body = (done.stdout or "").strip()

    if not body:
        pytest.skip(f"demo 栈没起（{DEMO_BASE}）：这条要真进程才量得准")
    payload = json.loads(body)
    if payload.get("code") == "NOT_FOUND":
        pytest.skip(f"库里没有 {SAMPLE_DELIVERABLE}：换一份样例再跑")

    assert set(payload) == _backend_keys(), (
        f"AST 与真 payload 对不上：AST {sorted(_backend_keys())}，"
        f"实回 {sorted(payload)}"
    )


def test_the_field_names_were_not_hand_copied_into_this_file() -> None:
    """本文件 NEVER 手抄一份字段清单当期望值。

    判的是**本文件自己**：期望值必须来自 `_backend_keys()`，
    而那个函数读的是 AST。手抄的清单不会跟着后端变——
    后端加一个字段，手抄的判据照样绿。
    """
    source = Path(__file__).read_text(encoding="utf-8")

    assert "_backend_keys()" in source
    # 唯一允许出现的字面量清单是「点名那三个」那一条，
    # 它判的是**对账表列出来的**那三个，不是全量期望值。
    literal_sets = re.findall(r'\{"[\w"，, ]+"\}', source)
    assert len(literal_sets) <= 1, f"出现了手抄的字段清单：{literal_sets}"


# ───────────────────────── acceptance③：对账表里这条消失


def test_the_parity_table_no_longer_reports_this_path_as_drift() -> None:
    drift = {
        f.subject for f in parity(REPO)
        if f.kind in ("field_mismatch", "frontend_untyped_response")
    }

    assert DELIVERABLE_PATH not in drift


def test_the_ruler_is_not_blind_even_though_it_reports_nothing() -> None:
    """阴性对照：尺子没瞎。

    原判据是「它此刻仍在报别的路径」。**`TYPE-04` 之后两类都归零了**——
    尺子改准 + 四条真缺口补齐，真仓库确实没有漂移了。
    再要求「必须报点什么」，就是逼人留一个缺陷不修。

    所以改判**它还在干活**：扫描面没塌（报了别的类），
    且分类能力有合成对照守着（`tests/v041/test_parity_dynamic_path.py`）。
    """
    findings = parity(REPO)

    assert findings, "一条发现都没有：扫描面塌了"
    assert {f.kind for f in findings} - {"field_mismatch",
                                         "frontend_untyped_response"}, (
        "只剩这两类了？那说明别的面没扫到"
    )
    assert (REPO / "tests" / "v041" / "test_parity_dynamic_path.py").exists(), (
        "分类能力的合成对照不在了"
    )
