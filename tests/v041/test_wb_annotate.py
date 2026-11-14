"""WB-06：五模板切换 + 单块批注重写（走干预层，NEVER 另开一条生成路）。

## 重写这条路**实跑过**（真栈 + 真库 + 本机 Ollama）

```
POST /deliverables/del-job-4d22d6be-…/sections/market/regenerate?project_id=proj-demo-fixture
     {"block_id": "…market-1", "guidance": "把这一段写得更具体一点…"}
→ 200 {"job_id": "job-ed52221b-…"}
库里：deliverables 多出 version=2 · supersedes=原件；那一块的正文换了；
      generation_records 记着 {"action":"regenerate_block","block_id":…,"guidance":…}
```

## 而它**不写事件、也不推作业状态**（本卡逮到的那条）

同一次实测：`jobs.state` 十分钟后仍是 `queued`，`job_events` **0 行**。
于是「作业结束了没有」这件事在今天的数据面上问不出来——
既有的 `InstructionRegenerateBox` 正是靠订阅事件流收尾的，照着用屏上就会一直转。
单：`docs/blocked/REGENERATE-JOB-WRITES-NO-EVENTS.md`（含三条修法与各自代价）。

我先写的绕行是「轮项目的交付物清单，新出现的那一份就是产物」——**实测那条路也不通**：
`GET /projects/{id}` 的 `deliverable_ids` 是建项时写死的一列，
组稿与重写落库都不回写它（库里四份，那一列一条）。
单：`docs/blocked/PROJECT-DOES-NOT-LIST-ITS-OWN-DELIVERABLES.md`。

于是屏上**只说到「已提交」为止**，且把作业 id 留在 `data-*` 上。
产物是真的（本文件的判据直接去库那一侧核它），只是这一屏够不着。
判据因此分两层：**屏那一层**判「提交对了、说了实话、没假装知道结果」；
**产物那一层**判「真的多出一版、且只有那一块变了」。
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PROBE = REPO / ".ui-probe" / "wb"
REPORT = PROBE / "annotate.json"
PWENV = Path(r"C:\pwenv\Scripts\python.exe")

WEB = REPO / "web"
ANNOTATE = WEB / "components" / "workbench" / "WorkbenchAnnotate.tsx"
PICKER = WEB / "components" / "workbench" / "WorkbenchTemplatePicker.tsx"
PREVIEW = WEB / "components" / "workbench" / "WorkbenchPreview.tsx"
PAGE = WEB / "app" / "workbench" / "page.tsx"
BLOCK_VIEW = WEB / "components" / "blocks" / "BlockView.tsx"
TICKET = REPO / "docs" / "blocked" / "REGENERATE-JOB-WRITES-NO-EVENTS.md"
PROBE_TOOL = REPO / "tools" / "ui_probe_wb_annotate.py"

_INPUTS = (ANNOTATE, PICKER, PREVIEW, PAGE, WEB / "app" / "globals.css", PROBE_TOOL)


def _inputs_stamp() -> str:
    import hashlib

    h = hashlib.sha256()
    for path in _INPUTS:
        h.update(path.read_bytes() if path.exists() else b"")
    return h.hexdigest()[:16]


def _report() -> dict[str, object]:
    if REPORT.exists():
        cached = json.loads(REPORT.read_text(encoding="utf-8"))
        if cached.get("inputs_stamp") == _inputs_stamp():
            return dict(cached)
        REPORT.unlink()
    if not PWENV.exists():
        pytest.skip(f"本机没有 {PWENV}（playwright 恒在项目外）")
    PROBE.mkdir(parents=True, exist_ok=True)
    done = subprocess.run(
        [str(PWENV), str(PROBE_TOOL)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=REPO, check=False)
    if done.returncode != 0 or not REPORT.exists():
        pytest.skip(f"真栈没起或探针跑不动：{(done.stderr or done.stdout)[-600:]}")
    got = json.loads(REPORT.read_text(encoding="utf-8"))
    got["inputs_stamp"] = _inputs_stamp()
    REPORT.write_text(json.dumps(got, ensure_ascii=False, indent=1), encoding="utf-8")
    return dict(got)


# ═════════════════ 一、模板切换：五套任选，导航与预览同步换


def test_the_picker_offers_exactly_the_five_generated_templates() -> None:
    """下拉里的五个选项**来自那份生成表**，NEVER 在这里列一遍。

    列一遍的话，某天多一套模板时下拉里不会有它，而屏上看起来一切正常。
    """
    code = PICKER.read_text(encoding="utf-8")

    assert "TEMPLATE_IDS" in code
    stripped = re.sub(r"/\*.*?\*/|//[^\n]*", "", code, flags=re.DOTALL)
    for template_id in ("generic", "startup", "engineering", "grant", "thesis"):
        assert template_id not in stripped, f"下拉里手写了模板 id：{template_id}"


def test_switching_the_template_switches_the_section_nav() -> None:
    """**正向 · 真栈**：在屏上切一次模板 → 章节导航换成那一套的章。"""
    m = _report()["switch"]

    assert m["from"] != m["to"], m
    assert list(m["idsBefore"]) != list(m["idsAfter"]), "切了模板而导航一个字没变"
    assert list(m["idsAfter"]) == list(m["expectedAfter"]), (
        f"切到 {m['to']} 之后导航是 {m['idsAfter']}，应是 {m['expectedAfter']}")


def test_the_two_columns_read_the_same_template_state() -> None:
    """导航与预览读的是**同一处**模板状态（切一次两边都换）。"""
    m = _report()["switch"]

    assert m["navTemplateAfter"] == m["to"], m
    assert m["pickerValueAfter"] == m["to"], m


# ═════════════════ 二、批注只重写一块，且走既有干预层


def test_the_annotation_goes_through_the_existing_intervention_client() -> None:
    """提交走 `interventionClient#regenerateBlockWithGuidance`，NEVER 另开一条生成路。

    两条生成路会让「这段文字是怎么来的」有两个答案。
    """
    code = ANNOTATE.read_text(encoding="utf-8")
    stripped = re.sub(r"/\*.*?\*/|//[^\n]*", "", code, flags=re.DOTALL)

    assert "regenerateBlockWithGuidance" in code
    assert "availableBlockInterventions" in code, "保护判定没走既有那一处"
    assert "/regenerate" not in stripped, "自己拼了重写端点的 URL"


def test_the_request_names_exactly_the_picked_block() -> None:
    """**正向 · 真栈**：发出去的那一发里，`block_id` 就是屏上点选的那一块，
    `guidance` 就是输入框里打的那句。

    「只重写这个块」这句话的可验形式就是这两格——
    只判「发出去了」的话，重写的是别的块也会绿。
    """
    m = _report()["submit"]

    assert m["method"] == "POST", m
    assert "/sections/" in str(m["url"]) and "/regenerate" in str(m["url"]), m["url"]
    assert m["sentBlockId"] == m["pickedBlockId"], (
        f"发的是 {m['sentBlockId']}，屏上点的是 {m['pickedBlockId']}")
    assert m["sentGuidance"] == m["typedGuidance"], m
    assert f"project_id={m['projectId']}" in str(m["url"]), m["url"]


def test_a_protected_block_cannot_be_annotated_and_says_why() -> None:
    """**阴性对照**（`S2-5`）：受保护的块改不动，且屏上**说清为什么**。

    藏起来不说的话，用户会以为这一块的批注功能坏了。
    """
    m = _report()["protected"]

    assert m["hasInput"] is False, "受保护的块还给了输入框"
    assert m["saysWhy"], f"没说为什么改不动：{m['text']}"


def test_an_unprotected_block_does_get_the_box() -> None:
    """两个方向各一次：**未受保护**的块给得出输入框与提交键。"""
    m = _report()["submit"]

    assert m["hadInput"], "未受保护的块也没有输入框——那这条路等于没通"


def test_the_frozen_renderer_was_not_touched_to_add_the_button() -> None:
    """蓝本把批注按钮放在每块旁边；本仓改成点选 + 面板，
    因为 `BlockView` 是 v0.4 已 verified 的封版件（`DEC-021`）。"""
    assert "WB-06" not in BLOCK_VIEW.read_text(encoding="utf-8"), (
        "BlockView 里出现了本卡的痕迹——它本不该被动")
    assert "closest" in PREVIEW.read_text(encoding="utf-8"), "点选没走事件委托"


# ═════════════════ 三、改写留痕：改了哪一块、批注是什么、到了哪一版


def test_the_rewrite_produced_a_new_version_that_supersedes_the_old_one() -> None:
    """**真产物**：重写产出**新版本**，且它接替了原来那一份。

    这是「改写前后留痕」在今天这条链上的形态：版本号涨在交付物那一层
    （v1 → v2 + `supersedes`）。取证是去**库那一侧**核的——
    屏上够不着它（三条路全断，见文件头），而产物是不是真的与屏够不够得着是两件事。
    """
    m = _report()["result"]

    assert m["newDeliverableId"], "库里没有多出重写产物——那这条路真的没通"
    assert m["newDeliverableId"] != m["oldDeliverableId"]
    assert int(m["newVersion"]) == int(m["oldVersion"]) + 1, m
    assert m["supersedes"] == m["oldDeliverableId"], m


def test_only_the_annotated_block_changed() -> None:
    """「**只重写这一个块**」的可验形式：新版本里只有那一块的正文变了。"""
    m = _report()["result"]

    assert list(m["changedBlockIds"]) == [m["pickedBlockId"]], (
        f"变的是 {m['changedBlockIds']}，批注对着的是 {m['pickedBlockId']}")


def test_the_screen_says_what_was_changed_and_with_what_annotation() -> None:
    """屏上留痕：改了哪一块、批注是什么。"""
    m = _report()["result"]

    assert m["pickedBlockId"] in str(m["screenText"]), m["screenText"][:200]
    assert m["typedGuidance"] in str(m["screenText"]), m["screenText"][:200]


def test_the_screen_stops_at_submitted_and_does_not_pretend_to_know_more() -> None:
    """屏上**只说到「已提交」为止**，NEVER 假装知道它什么时候好。

    今天从「提交了」到「产物是哪一份」三条路全断（文件头那三张单）。
    这条判据钉的是**诚实态**：终态记号是 `submitted`，
    而且屏上那句话自己说清了「这一版看不到它什么时候好」。
    """
    m = _report()["result"]
    messages = json.loads((WEB / "messages" / "zh.json").read_text(encoding="utf-8"))

    assert m["phase"] == "submitted", f"终态是 {m['phase']}"
    assert m["jobOnScreen"], "作业 id 一个字都没留下（连事后去查都无从查起）"
    tail = messages["wb.annotate.submitted"].split("。")[-2]
    assert tail in str(m["screenText"]), f"屏上没说清这一版看不到结果：{m['screenText'][:200]}"


def test_block_level_revision_did_not_move_and_that_is_registered() -> None:
    """`revision +1` 那一条**今天不成立**，而它有单、不是被判据放过去的。

    工单要的是「未受保护的改得动且 revision +1」。实测：改得动（新版本、正文换了），
    而 22 块的 `revision` 全是 1——版本号涨在交付物那一层。
    这条判据钉住的是**实况与单子一致**：哪天块级 revision 真的涨了，
    它会当场红，提醒来这里改判据、去单子里销账。
    """
    m = _report()["result"]

    assert int(m["newBlockRevision"]) == int(m["oldBlockRevision"]), (
        f"块级 revision 动了（{m['oldBlockRevision']} → {m['newBlockRevision']}）——"
        f"实况变了，来这里改判据并销掉 {TICKET.name} 里那一段")
    assert TICKET.exists(), "那条实况的单子不在盘上"
    assert "revision" in TICKET.read_text(encoding="utf-8"), "单子里没写这一格"


# ═════════════════ 四、那条绕行本身的形状（NEVER 当成修好了）


def test_the_screen_does_not_poll_the_job_state_because_it_never_moves() -> None:
    """屏上**不轮询作业状态**：它永远是 `queued`，轮它就是一直转。

    判据钉的是这条路的形状：批注这一处不出现 `fetchJobSnapshot`/`openJobStream`，
    也不去轮项目总览（那条绕行实测不成立，见文件头）。
    """
    code = ANNOTATE.read_text(encoding="utf-8")
    stripped = re.sub(r"/\*.*?\*/|//[^\n]*", "", code, flags=re.DOTALL)

    assert "fetchJobSnapshot" not in stripped and "openJobStream" not in stripped
    assert "/projects/" not in stripped, "又去轮项目总览了——那一列不会变"


def test_the_seam_for_switching_to_the_new_version_is_still_there() -> None:
    """解阻那天要接回来的那条缝**留着**（`onNewVersion`），且写明今天没有调用点。

    删掉的话，下一个人会以为这一屏本来就不打算换预览——
    而那正是三张单解开之后第一件该做的事。
    """
    code = ANNOTATE.read_text(encoding="utf-8")

    assert "onNewVersion" in code
    assert "今天没有调用点" in code, "留了缝却没写它为什么空着"


@pytest.mark.parametrize("theme", ("light", "dark"))
def test_the_screenshot_is_on_disk(theme: str) -> None:
    matches = list(PROBE.glob(f"workbench-annotate-*-{theme}.png"))

    assert matches, f"缺这一张：{theme}"
    assert matches[0].stat().st_size > 10_000, (
        f"{matches[0].name} 只有 {matches[0].stat().st_size} 字节")
