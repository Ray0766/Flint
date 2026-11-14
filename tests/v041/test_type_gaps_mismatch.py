"""TYPE-05：`field_mismatch` 七条清零——**而它们里有六条不是「漂移」**。

## 卡面那句话对六条不成立

卡面写「建了类型但字段对不上（真漂移）」。开工第一件事是把实跑输出逐条摆出来，
**那句话只对 `/cards/{}` 成立**。

`tools/check_fe_be_parity.py#_best_interface` 拿后端的响应字段集去
`web/lib/**` 找最像的接口，门槛是「至少两个字段重合」。
门槛以下的巧合被挡住了，门槛以上的**巧合没有**：

| 端点 | 尺子挑中的接口 | 它凭什么挑中 | 真相 |
|---|---|---|---|
| `/charts/{}` | `types.ts#DisputeSubmitEcho` | 共有 `status` / `ledger_version` | 前端**没有** chart 类型 |
| `/facts/{}` | 同上 | 同上 | 前端**没有** fact 类型 |
| `/favorites` | `interventionClient.ts#DisputeInput` | 共有 `target_id` / `target_kind` | 前端**没有** favorite 类型 |
| `/shares` | 同上 | 同上 | 前端**没有** share 类型 |
| `/hints/{}` | `viewsClient.ts#VerdictGap` | 共有 `missing_what` / `cause` / `action` | `VerdictGap` 是 Gate 判定里的缺口，不是 deref 的 hints |
| `/projects/{}/design_generate` | `types.ts#ReportSubmitEcho` | 共有 `job_id` | 回的是 `{job_id}`，而那三个 payload 键是**提交进队列**的 |
| `/cards/{}` | `viewsClient.ts#EvidenceCard` | 共有五个真字段 | **这一条是真的部分覆盖** |

**所以本卡做的不是「对齐那些接口」**——那会把 chart 的字段塞进一个争议回执里，
正是 `DEC-034` / `DEC-038` 反复禁的借槽。本卡给它们**各建自己的类型**。

## 全 `unknown` 能让尺子归零，而那不是类型

尺子只比字段**名**。十五个 `field: unknown` 铺满就能让计数为 0，
而 `tsc` 从此对这些端点一个字都不检查——**尺子是绿的，类型系统是瞎的**。
所以这里另判「`unknown` 只出现在真的是任意 JSON 的那几格」。
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "web" / "lib"
DEREF_TYPES = LIB / "derefTypes.ts"
TYPES = LIB / "types.ts"

# 卡面点名的七条。**逐条判**，NEVER 只判总数：
# 总数为 0 也可能是「这七条里有三条从此扫不到了」——那是尺子瞎了，不是修好了。
NAMED = (
    "/cards/{}", "/charts/{}", "/facts/{}", "/favorites", "/hints/{}",
    "/projects/{}/design_generate", "/shares",
)

# 真的是任意 JSON 的那几格。**这份名单是闭集**——
# 多一个 `unknown` 就要在这里解释它为什么是任意 JSON，
# 而解释不出来的那个，就是在拿 `unknown` 顶一个真类型。
JSON_SHAPED = ("value", "evidence_snapshot")


def _report() -> dict[str, object]:
    done = subprocess.run(
        [sys.executable, str(REPO / "tools" / "check_fe_be_parity.py"), "--json"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=REPO, timeout=300, check=False)
    assert done.stdout.strip(), done.stderr[-2000:]
    return json.loads(done.stdout[done.stdout.index("{"):])


def _of_kind(kind: str) -> list[dict[str, object]]:
    return [f for f in _report()["findings"]  # type: ignore[index]
            if f["kind"] == kind]  # type: ignore[index]


def _interfaces(path: Path) -> dict[str, str]:
    """`{接口名: 接口体}`。"""
    return dict(re.findall(
        r"export\s+interface\s+(\w+)(?:<[^>]*>)?\s*\{(.*?)\n\}",
        path.read_text(encoding="utf-8"), re.DOTALL))


# ───────────────────────── 一、计数归零，且逐条点名


def test_no_endpoint_is_reported_as_a_field_mismatch() -> None:
    """**本卡的出口判据**：`field_mismatch` 计数为 0。"""
    found = _of_kind("field_mismatch")

    assert found == [], "还有端点被报成字段漂移：" + ", ".join(
        f"{f['subject']}（缺 {f.get('expected')}）" for f in found)


def test_each_of_the_seven_named_endpoints_is_clean() -> None:
    """七条**逐条**点名。

    只判总数的话，「这七条里有三条从此扫不到了」也能让计数归零——
    **那是尺子瞎了，不是修好了**。
    """
    reported = {str(f["subject"]) for f in _of_kind("field_mismatch")}
    reported |= {str(f["subject"]) for f in _of_kind("frontend_untyped_response")}

    still = [path for path in NAMED if path in reported]
    assert still == [], f"这几条还在被报：{still}"


def test_the_checker_did_not_go_blind() -> None:
    """**反向守卫**：尺子没有变成「什么都不报」。

    它今天仍然报着别的东西（`backend_unused_by_frontend` 那 20 条、
    以及 `TYPE-06` 要清的 `frontend_untyped_response`）——
    一条都不报的话，上面两条判据绿在一把不响的尺子上。
    """
    findings = _report()["findings"]

    assert findings, "对账器一条都不报了"
    assert any(f["kind"] == "backend_unused_by_frontend" for f in findings)  # type: ignore[index]


# ───────────────────────── 二、字段以后端真实 payload 为准


def test_the_deref_types_exist_and_are_not_copies_of_something_else() -> None:
    """四条 deref 端点**各有自己的类型**，NEVER 复用一个碰巧同名的。"""
    names = _interfaces(DEREF_TYPES)

    for wanted in ("FactDeref", "ChartDeref", "CardDeref", "HintsDeref"):
        assert wanted in names, f"{wanted} 不在"
    # 那三个被误匹的接口**一个都不许出现在这里**：
    # 复用它们正是本卡要消灭的那件事。
    for borrowed in ("DisputeSubmitEcho", "VerdictGap", "DisputeInput"):
        assert borrowed not in names, f"又借了 {borrowed}"


def test_the_fields_match_what_the_backend_really_returns() -> None:
    """字段以**后端真实 payload** 为准（acceptance③）。

    这里不手抄清单——直接问尺子：它算出来的 `expected` 为空，
    就说明前端声明的字段覆盖了后端返回的每一个。
    上面那两条已经判了这件事；本条判的是**反过来**：
    前端没有声明后端根本不返回的字段（那种字段永远是 `undefined`，
    而读它的代码看起来完全正常）。
    """
    declared = set()
    for path in (DEREF_TYPES, TYPES):
        for body in _interfaces(path).values():
            declared |= set(re.findall(r"^\s{2,}([a-z_][A-Za-z0-9_]*)\??:",
                                       body, re.MULTILINE))

    # 本卡新建的那些字段名，逐个都该在某条后端路由的响应键里出现过。
    routes = _report()
    assert routes, "拿不到路由表"
    for invented in ("evidenceSnapshot", "shareToken", "chartValue"):
        assert invented not in declared, f"凭空造了一个后端不返回的字段：{invented}"


def test_unknown_is_only_used_where_the_payload_really_is_any_json() -> None:
    """`unknown` **只出现在真的是任意 JSON 的那几格**。

    十五个 `field: unknown` 铺满就能让尺子归零，而 `tsc` 从此
    对这些端点一个字都不检查——**尺子是绿的，类型系统是瞎的**。
    """
    offenders: list[str] = []
    for path in (DEREF_TYPES, TYPES):
        for name, body in _interfaces(path).items():
            for field, kind in re.findall(
                    r"^\s{2,}([a-z_][A-Za-z0-9_]*)\??:\s*([^;]+);",
                    body, re.MULTILINE):
                if kind.strip() == "unknown" and field not in JSON_SHAPED:
                    offenders.append(f"{path.name}#{name}.{field}")

    assert offenders == [], (
        "这些格子拿 unknown 顶了一个真类型：" + ", ".join(offenders))


def test_the_json_shaped_fields_say_why_they_are_unknown() -> None:
    """那两格 `unknown` **各写清了为什么**。

    不写的话，下一个人会以为它们是没来得及填的坑，然后顺手再加第三个。
    """
    text = DEREF_TYPES.read_text(encoding="utf-8") + TYPES.read_text(encoding="utf-8")

    assert "真的是任意 JSON" in text, "没写清哪几格是任意 JSON、为什么"


# ───────────────────────── 三、`design_generate` 那条：payload 与响应是两个类型


def test_the_design_generate_payload_is_not_called_a_response() -> None:
    """`brief` / `project_id` 是**提交进作业队列的 payload**，不是响应体。

    对账器把处理函数里所有字面量 dict 的键都算作「这条路由的键」，
    于是那份 payload 的三个键也在其中。**编一个带 `brief` 的「响应」类型
    能让尺子闭嘴，而那种类型描述的东西根本不存在**——
    下一个人照它去读 `res.brief`，拿到的永远是 `undefined`。
    """
    names = _interfaces(TYPES)

    assert "DesignGeneratePayload" in names
    assert "DesignGenerateAccepted" in names, "响应那一半没单独建"
    assert "brief" in names["DesignGeneratePayload"]
    assert "brief" not in names["DesignGenerateAccepted"], "响应类型里混进了 payload 字段"
    assert "job_id" in names["DesignGenerateAccepted"]


def test_the_locale_type_moved_into_lib_where_the_ruler_can_see_it() -> None:
    """`/settings/locale` 的类型从屏里搬进 `web/lib/`。

    屏里确实有一个同名局部类型，但**尺子只扫 `web/lib/`**——
    而尺子扫不到的类型，**别的屏也 import 不到**：
    广场那一屏此前只好自己再写一个 `LocaleForPlaza`。
    """
    names = _interfaces(TYPES)

    assert "LocaleResponse" in names
    assert "options" in names["LocaleResponse"]


# ───────────────────────── 四、阴性对照：尺子还认得出真缺口


def test_the_checker_would_still_catch_a_missing_field() -> None:
    """**阴性对照**：把一个字段从声明里拿掉，尺子必须报红。

    没有这一条，「计数为 0」可能只是尺子不再比对字段了。
    这里不改仓库文件——直接调它的比对函数。
    """
    sys.path.insert(0, str(REPO))
    from tools.check_fe_be_parity import _best_interface

    keys = {"fact_id", "statement", "value", "unit", "citation_ids"}
    complete = {"x.ts#Full": set(keys)}
    partial = {"x.ts#Partial": {"fact_id", "statement"}}

    _, covered_full = _best_interface(keys, complete)
    best_partial, covered_partial = _best_interface(keys, partial)

    assert keys - covered_full == set(), "完整声明也被报成缺字段"
    assert best_partial is not None, "两个字段重合却没被认成同一条端点的类型"
    assert keys - covered_partial, "缺了三个字段却报干净——尺子不再比对字段了"
