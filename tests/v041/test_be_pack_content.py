"""BE-02：vibe_pack 内容读取端点 `GET /deliverables/{id}/pack`（蓝本 P12「内容端点未接」）。

## 补的是什么

蓝本路由表 P12 那一行写着**「内容端点未接（pack 装配仅离线）」**——
vibe_pack 查看器拿不到内容，因为装配只在离线跑，没有读的口。
本卡把**已装配好的产物**做成一个可读端点。

## 只读装配产物，NEVER 在端点里现场装配

装配是 job 的事：它要跑门禁、要算 contracts 副本哈希、要过 S2-8 自检。
放进一个 GET 里的话，**一次刷新页面就跑一遍装配**，而且装出来的东西
与导出那份可能不是同一份（两次装配之间源变了）。

所以本端点只读 `PackBundle`，**不调 `assemble_pack`、不调 `build_zip`**。

## 产物不存在时返回「尚未生成」态，而不是 404

acceptance② 逐字写死。理由与 BE-01 的空态同源：
**404 说的是「没这个交付物」，而这里交付物是在的，只是 pack 还没装**。
两者混在一起时，用户会以为自己的交付物丢了。

## NEVER 造字段

返回的每一项都来自 `PackBundle` 与 `ContractsCopy` 的真字段。
章节清单是从 markdown 里**数出来的**，不是写死的九个字符串——
写死的话，装配少了一章这里照样报九章。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from flint.api.pack import PackApiDeps, create_pack_app
from flint.spec.contracts_copy import ContractsCopy
from flint.spec.pack_zip import PackBundle

MODULE = REPO / "flint" / "api" / "pack.py"

OWNER = "u-be02"
STRANGER = "u-other"

CLAUDE_MD = "\n\n".join(
    f"## S{i} 第{i}章\n\n正文{i}" for i in range(1, 10)
)


def _bundle() -> PackBundle:
    return PackBundle(
        claude_md=CLAUDE_MD,
        human_digest="## 附：Human Digest\n\n监工视图",
        tasks_json='{"tasks": [{"id": "T-1"}, {"id": "T-2"}]}',
        contracts=ContractsCopy(
            files={"models.py": b"x = 1\n", "protocols.py": b"y = 2\n"},
            manifest={"models.py": "aa", "protocols.py": "bb"},
            readme="冻结件副本，只读",
        ),
    )


def _client(
    *, bundle: PackBundle | None = None, owner: str = OWNER, known: bool = True,
) -> TestClient:
    async def builder(deliverable_id: str) -> PackBundle:
        del deliverable_id
        assert bundle is not None, "端点在没有产物时不该去要 bundle"
        return bundle

    async def gate_inputs(deliverable_id: str) -> object:
        raise AssertionError("读内容 NEVER 走导出门禁：那是导出面的事")

    async def owner_of(deliverable_id: str) -> str | None:
        del deliverable_id
        return owner if known else None

    async def has_pack(deliverable_id: str) -> bool:
        del deliverable_id
        return bundle is not None

    deps = PackApiDeps(
        dsn="postgresql://unused", bundle_builder=builder,
        gate_inputs=gate_inputs,  # type: ignore[arg-type]
        pack_owner=owner_of, pack_ready=has_pack,
    )
    return TestClient(create_pack_app(deps))


# ───────────────────────── 一、内容读得到（acceptance①）


def test_the_pack_content_endpoint_exists() -> None:
    response = _client(bundle=_bundle()).get(
        "/deliverables/d-1/pack", headers={"X-User-Id": OWNER})

    assert response.status_code == 200


def test_it_returns_the_nine_chapters() -> None:
    """S1~S9 章节族**逐章给出**，前端不必自己切 markdown。"""
    body = _client(bundle=_bundle()).get(
        "/deliverables/d-1/pack", headers={"X-User-Id": OWNER}).json()

    assert [c["id"] for c in body["chapters"]] == [f"S{i}" for i in range(1, 10)]
    assert body["chapters"][0]["body"].startswith("## S1 ")


def test_the_chapter_list_is_counted_not_hardcoded() -> None:
    """章节是从 markdown 里**数出来的**。

    写死九个字符串的话，装配少了一章这里照样报九章——
    而读的人以为自己拿到的是全本。
    """
    short = CLAUDE_MD.split("## S8 ")[0]
    body = _client(bundle=PackBundle(
        claude_md=short, human_digest="d", tasks_json="{}",
        contracts=_bundle().contracts)).get(
        "/deliverables/d-1/pack", headers={"X-User-Id": OWNER}).json()

    assert [c["id"] for c in body["chapters"]] == [f"S{i}" for i in range(1, 8)]


def test_markdown_without_chapter_heads_yields_no_chapters() -> None:
    """切不出章时返回**空表**，NEVER 把整篇当成一章。

    当成一章的话，前端会显示一个叫「S1」的章节，内容是整本 CLAUDE.md——
    看起来像装配成功了，实际是章头全丢了（变异考② 实测）。
    """
    body = _client(bundle=PackBundle(
        claude_md="没有任何章头的一段文字", human_digest="d", tasks_json="{}",
        contracts=_bundle().contracts)).get(
        "/deliverables/d-1/pack", headers={"X-User-Id": OWNER}).json()

    assert body["chapters"] == []


def test_it_returns_the_tasks_list() -> None:
    """机读任务清单一并给出——vibe_pack 查看器要并排显示章节与任务。"""
    body = _client(bundle=_bundle()).get(
        "/deliverables/d-1/pack", headers={"X-User-Id": OWNER}).json()

    assert [t["id"] for t in body["tasks"]] == ["T-1", "T-2"]


def test_it_returns_the_contracts_file_list_with_hashes() -> None:
    """冻结件副本**只给清单与哈希，不给内容**。

    副本内容是二进制、动辄几十 KB，塞进一个 JSON 里既没人看也拖慢每次打开。
    要看内容走导出那条路（zip 里有）。
    """
    body = _client(bundle=_bundle()).get(
        "/deliverables/d-1/pack", headers={"X-User-Id": OWNER}).json()

    assert sorted(f["name"] for f in body["contracts"]) == ["models.py", "protocols.py"]
    assert all(f["sha256"] for f in body["contracts"])
    assert all("content" not in f for f in body["contracts"])


def test_the_human_digest_is_marked_as_not_for_ai_context() -> None:
    """Human Digest 是**监工视图**，`pack_assemble` 原话「NEVER 并入 markdown」。

    给出去时要带那个标记，否则前端会把它和九章一起喂进上下文。
    """
    body = _client(bundle=_bundle()).get(
        "/deliverables/d-1/pack", headers={"X-User-Id": OWNER}).json()

    assert body["human_digest"]["for_ai_context"] is False


# ───────────────────────── 二、只读产物，NEVER 现场装配（acceptance②）


def test_the_module_never_assembles_on_the_read_path() -> None:
    """端点里 NEVER 调装配器。

    装配要跑门禁、算副本哈希、过 S2-8 自检；放进一个 GET 里的话，
    一次刷新就跑一遍，而且装出来的可能与导出那份不是同一份。
    """
    import ast

    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    called = {
        node.func.id if isinstance(node.func, ast.Name) else
        (node.func.attr if isinstance(node.func, ast.Attribute) else "")
        for node in ast.walk(tree) if isinstance(node, ast.Call)
    }

    for banned in ("assemble_pack", "assemble_s3_contracts", "build_contracts_copy"):
        assert banned not in called, f"读内容那条路调了装配器：{banned}"


def test_reading_content_does_not_run_the_export_gate() -> None:
    """读内容不过导出门禁——门禁是导出面的事（本判据的 `gate_inputs` 一被调就抛）。"""
    response = _client(bundle=_bundle()).get(
        "/deliverables/d-1/pack", headers={"X-User-Id": OWNER})

    assert response.status_code == 200


def test_a_deliverable_without_a_pack_reports_not_generated_not_404() -> None:
    """acceptance②：产物不存在 → **「尚未生成」态**，不是 404。

    404 说的是「没这个交付物」，而这里交付物是在的，只是 pack 还没装。
    混在一起时，用户会以为自己的交付物丢了。
    """
    response = _client(bundle=None).get(
        "/deliverables/d-1/pack", headers={"X-User-Id": OWNER})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "not_generated"
    assert body["chapters"] == []
    assert body["tasks"] == []


def test_a_generated_pack_says_so_too() -> None:
    """反向：装好了要说「已生成」——只在没有时说话的话，读的人得靠推断。"""
    body = _client(bundle=_bundle()).get(
        "/deliverables/d-1/pack", headers={"X-User-Id": OWNER}).json()

    assert body["status"] == "generated"


# ───────────────────────── 三、多租户与 404（acceptance③④）


def test_another_owners_pack_is_404_not_403() -> None:
    """**状态码本身就泄露存在性**：403 等于确认了这个 id 存在。"""
    response = _client(bundle=_bundle(), owner=STRANGER).get(
        "/deliverables/d-1/pack", headers={"X-User-Id": OWNER})

    assert response.status_code == 404


def test_an_unknown_deliverable_is_404() -> None:
    response = _client(bundle=_bundle(), known=False).get(
        "/deliverables/nope/pack", headers={"X-User-Id": OWNER})

    assert response.status_code == 404


def test_the_two_kinds_of_404_are_indistinguishable() -> None:
    """「不存在」与「不该看到」对外长得一样——差一个字都能被用来枚举 id。"""
    unknown = _client(bundle=_bundle(), known=False).get(
        "/deliverables/nope/pack", headers={"X-User-Id": OWNER})
    forbidden = _client(bundle=_bundle(), owner=STRANGER).get(
        "/deliverables/d-1/pack", headers={"X-User-Id": OWNER})

    assert unknown.status_code == forbidden.status_code
    assert unknown.json()["code"] == forbidden.json()["code"]


def test_the_owner_still_sees_their_own() -> None:
    """反向：本人照样看得见。见谁都 404 的隔离等于把功能关掉。"""
    response = _client(bundle=_bundle(), owner=STRANGER).get(
        "/deliverables/d-1/pack", headers={"X-User-Id": STRANGER})

    assert response.status_code == 200


def test_identity_is_required() -> None:
    response = _client(bundle=_bundle()).get("/deliverables/d-1/pack")

    assert response.status_code == 422


def test_an_app_built_without_the_owner_check_serves_nothing() -> None:
    """**没注入归属判定就不给内容**——那时任何人都能读任何 pack。

    这条不是假设：既有装配点（M4-028）构造 `PackApiDeps` 时只给三项，
    两个新字段默认 `None`。如果那种 app 照样交出内容，
    等于本卡在所有既有部署上开了一个无鉴权的读口（变异考⑧ 实测）。
    """
    async def builder(deliverable_id: str) -> PackBundle:
        del deliverable_id
        raise AssertionError("没注入归属判定时不该去要 bundle")

    async def gate_inputs(deliverable_id: str) -> object:
        raise AssertionError("读内容 NEVER 走导出门禁")

    legacy = TestClient(create_pack_app(PackApiDeps(
        dsn="postgresql://unused", bundle_builder=builder,
        gate_inputs=gate_inputs)))  # type: ignore[arg-type]

    response = legacy.get("/deliverables/d-1/pack", headers={"X-User-Id": OWNER})

    assert response.status_code == 404


def test_every_404_on_the_content_path_uses_the_same_error_code() -> None:
    """读内容那条路上的**每一个** 404 都用 `NOT_FOUND`。

    「不存在」「不该看到」「没注入鉴权」三种情况在我的实现里走同一行，
    所以逐条比状态码杀不掉「换个错误码」那种改动——它会把三处一起改掉
    （变异考⑯ 实测）。这一条改成打在**源码**上：那条路上出现
    `_error(404, ...)` 而 code 不是 `NOT_FOUND` 即红。
    """
    import ast

    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    handler = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "pack_content"
    )

    codes = [
        ast.unparse(call.args[1])
        for call in ast.walk(handler)
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
        and call.func.id == "_error" and len(call.args) >= 2
        and ast.unparse(call.args[0]) == "404"
    ]

    assert codes, "读内容那条路一个 404 都没有"
    assert set(codes) == {"'NOT_FOUND'"}, f"404 用了不同的错误码：{sorted(set(codes))}"


# ───────────────────────── 四、只读 + NEVER 造字段（acceptance③⑤）


def test_the_read_path_never_writes() -> None:
    """阴性对照：模块里 NEVER 出现写库语句（判在去掉 docstring 之后的字面量上）。"""
    import ast

    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    docstrings = {ast.get_docstring(n) for n in ast.walk(tree)
                  if isinstance(n, ast.Module | ast.ClassDef | ast.FunctionDef
                                | ast.AsyncFunctionDef)}
    literals = " ".join(
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        and node.value not in docstrings
    )

    for verb in ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER"):
        assert not re.search(rf"\b{verb}\b", literals, re.IGNORECASE), f"模块里有 {verb}"


def test_every_returned_key_comes_from_the_bundle() -> None:
    """**NEVER 造字段**：返回的每一项都能在 `PackBundle` / `ContractsCopy` 里找到来源。"""
    body = _client(bundle=_bundle()).get(
        "/deliverables/d-1/pack", headers={"X-User-Id": OWNER}).json()

    assert set(body) == {
        "deliverable_id", "status", "chapters", "human_digest", "tasks", "contracts",
    }


def test_no_quality_score_is_synthesised() -> None:
    """NEVER 合成「完整度 8/9 章」这类分值——前端因此画不出进度条。

    章节数是**计数**，不是分值；把它除以 9 变成百分比是前端要做的事，
    而本端点连那个分母都不给（少一章是内容问题，不是「完成度 89%」）。
    """
    import json as _json

    flat = _json.dumps(_client(bundle=_bundle()).get(
        "/deliverables/d-1/pack", headers={"X-User-Id": OWNER}).json(), ensure_ascii=False)

    for invented in ("percent", "score", "completeness", "ratio", "health"):
        assert invented not in flat, f"合成了一个算不出的字段：{invented}"


# ───────────────────────── 五、既有导出面不倒


def test_the_existing_render_endpoint_still_exists() -> None:
    """导出面还在——**但它已经不在本模块了**（`ROUTE-01`）。

    改前这条判「`pack.py` 里那条 `/render` 一行没动」，量的是
    「加一个读的口，不要顺手改坏导出」。那个意思现在要在**赢家**身上量：
    `pack.py` 与 `deliverables.py` 曾各注册同一条路径，`ROUTE-01` 按 owner
    裁决把它收敛到 `deliverables.py`，三与门一起搬过去。

    继续判本模块的话，这条会**逼着人把冲突再造回来**。
    """
    winner = (MODULE.parent / "deliverables.py").read_text(encoding="utf-8")

    assert '@app.get("/deliverables/{deliverable_id}/render")' in winner
    assert "vibe_export_gate" in winner, "门禁没跟着搬过来"
    assert "build_zip" in winner
    # 输家那侧：**路由没了，类型还在**（`GateInputs` 是赢家 import 的那一份）。
    source = MODULE.read_text(encoding="utf-8")
    assert '@app.get("/deliverables/{deliverable_id}/render")' not in source
    assert "class GateInputs" in source


@pytest.mark.parametrize("marker", ["EXPORT_BLOCKED", "application/zip"])
def test_the_export_path_keeps_its_contract(marker: str) -> None:
    """出件契约（409 的码 / zip 的 content-type）跟着搬进赢家，一个字没改。"""
    assert marker in (MODULE.parent / "deliverables.py").read_text(encoding="utf-8")
