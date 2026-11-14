"""CAL-01：金标集标注（DeepSeek 代判 θ_rel / δ / 血缘）。

## 本卡只产出标注，NEVER 调阈值

θ_rel（0.6）、δ、血缘线都是 `CLAUDE.md#S4` 的未决项。**调参是 CAL-02**。
本模块里因此**一个阈值常量都没有**——有断言按 AST 扫着。
内置了阈值，标出来的金标就带着当前阈值的偏见，用它去调那个阈值，
等于**拿答案去验算答案**（`harness/gold_collect.py` 的原话）。

## 判准先落盘，再标注

acceptance②：**每轮标注前 MUST 先把判准写清并落盘**。
所以 `annotate()` 收的是**判准指纹**，指纹对不上盘上的判准文件就抛错——
「判准写在提示词里」与「判准落了盘」是两件事：前者跑完就没了，
后者是下一个人复核这批标注的唯一依据。

## 可复现：不是「结果一定一样」，是「不一样时看得见」

LLM 不保证逐字节复现。本模块的可复现是两件事：

1. **序列化确定**（固定键序 / 编码 / 行尾）——同一批标注两次落盘逐字节一致；
2. **两轮之间的差异被逐条报出来**（`diff_rounds`），而不是后一轮静默覆盖前一轮。

第 2 条才是关键：**静默覆盖会让「模型这次判得不一样」看起来像「一直就是这样」。**
"""
from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path

import pytest

from harness.gold_annotate import (
    KINDS,
    LABELS,
    Annotation,
    AnnotationItem,
    RubricNotOnDisk,
    annotate,
    build_prompt,
    diff_rounds,
    parse_label,
    rubric_fingerprint,
    to_jsonl,
    write_rubrics,
)

REPO = Path(__file__).resolve().parents[2]
GOLDSETS = REPO / "assets" / "goldsets"
NOW = "2026-08-04T20:00:00Z"


class _Provider:
    """替身 provider：测试恒回放，一次真实调用都没有。"""

    model = "deepseek-chat"

    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)
        self.prompts: list[str] = []
        self.purposes: list[str] = []

    def generate_with_purpose(self, prompt: str, *, purpose: str) -> object:
        self.prompts.append(prompt)
        self.purposes.append(purpose)
        reply = self._replies.pop(0)

        class _C:
            text = reply

        return _C()


def _item(kind: str = "relevance") -> AnnotationItem:
    payloads = {
        "relevance": {"cluster": "农业机器人", "candidate": "果园采摘机械臂"},
        "same_topic": {"left": "液冷集群调度", "right": "热感知任务编排"},
        "lineage": {"cluster": "农业机器人", "prev_day": "2026-06-29",
                    "day": "2026-06-30", "prev_cluster": "农业机器人",
                    "event_kind": "continued"},
    }
    return AnnotationItem(item_id=f"it-{kind}", kind=kind, payload=payloads[kind])


# ───────────────────────── 一、判准先落盘（acceptance②）


def test_three_kinds_each_have_a_rubric() -> None:
    """三类各有判准：没有判准的标注是「模型觉得」，不是标注。"""
    assert set(KINDS) == {"relevance", "same_topic", "lineage"}
    for kind in KINDS:
        assert len(rubric_fingerprint(kind)) == 64


def test_the_rubrics_land_on_disk_before_any_annotation(tmp_path: Path) -> None:
    """acceptance②：**先落盘，再标注**。"""
    written = write_rubrics(tmp_path)

    assert {p.name for p in written} == {f"{k}.md" for k in KINDS}
    for path in written:
        assert len(path.read_text(encoding="utf-8")) >= 100, f"{path.name} 判准太短"


def test_annotating_without_the_rubric_on_disk_is_refused(tmp_path: Path) -> None:
    """判准没落盘就标注 → 抛错。

    「判准写在提示词里」与「判准落了盘」是两件事：前者跑完就没了，
    后者是下一个人复核这批标注的唯一依据。
    """
    provider = _Provider(['{"label": "relevant"}'])

    with pytest.raises(RubricNotOnDisk):
        annotate(provider, [_item()], rubric_dir=tmp_path, now=lambda: NOW)


def test_a_tampered_rubric_is_caught(tmp_path: Path) -> None:
    """盘上的判准被改过 → 抛错，NEVER 按新判准记成旧指纹。

    不查的话，两轮标注会各按各的判准做，而记录上看起来是同一套。
    """
    write_rubrics(tmp_path)
    (tmp_path / "relevance.md").write_text("改过了", encoding="utf-8")
    provider = _Provider(['{"label": "relevant"}'])

    with pytest.raises(RubricNotOnDisk):
        annotate(provider, [_item()], rubric_dir=tmp_path, now=lambda: NOW)


# ───────────────────────── 二、标注本身（acceptance①③）


@pytest.mark.parametrize("kind", KINDS)
def test_the_prompt_carries_the_rubric_and_the_payload(kind: str) -> None:
    """判词里既有判准也有被标的东西——缺任一，标注都无从复核。"""
    item = _item(kind)
    prompt = build_prompt(item)

    for value in item.payload.values():
        assert str(value) in prompt
    assert "只输出 JSON" in prompt


@pytest.mark.parametrize("kind,label", [
    ("relevance", "relevant"), ("same_topic", "same"), ("lineage", "correct"),
])
def test_a_label_parses_into_the_closed_set(kind: str, label: str) -> None:
    """每类的标签是闭集：模型自创一个标签，下游没人知道怎么处置。"""
    assert parse_label(json.dumps({"label": label}), kind=kind) == label


@pytest.mark.parametrize("kind", KINDS)
def test_an_out_of_set_label_is_none_not_a_guess(kind: str) -> None:
    """越界标签记 `None`（未标注），**NEVER 挑一个最像的顶上**。"""
    assert parse_label(json.dumps({"label": "maybe"}), kind=kind) is None


@pytest.mark.parametrize("kind", KINDS)
def test_an_unparseable_reply_is_none(kind: str) -> None:
    """判词坏了记未标注，NEVER 记成某一类——那会让一次故障变成一条数据。"""
    assert parse_label("not json", kind=kind) is None


def test_every_annotation_carries_judge_time_and_rubric(tmp_path: Path) -> None:
    """acceptance③：**判官标识 + 时间戳 + 判准指纹**，三样缺一不可。

    少判准指纹的话，两轮标注按不同判准做出来，记录上看起来是同一套。
    """
    write_rubrics(tmp_path)
    provider = _Provider(['{"label": "relevant"}'])

    out = annotate(provider, [_item()], rubric_dir=tmp_path, now=lambda: NOW)

    assert out[0].judge == "deepseek-chat"
    assert out[0].judged_at == NOW
    assert out[0].rubric_sha == rubric_fingerprint("relevance")
    # 被标的东西也要带上。盘上那份产物的同名判据管不了这件事——
    # 它读的是已落盘的文件，改 `annotate()` 不会让它红（变异考实测：38 条全过）。
    assert out[0].payload == _item().payload


def test_the_purpose_tag_names_the_kind(tmp_path: Path) -> None:
    """用途标签带类别——账上要看得出这笔钱花在标哪一类上。"""
    write_rubrics(tmp_path)
    provider = _Provider(['{"label": "same"}'])

    annotate(provider, [_item("same_topic")], rubric_dir=tmp_path, now=lambda: NOW)

    assert provider.purposes == ["gold_annotate:same_topic"]


# ───────────────────────── 三、可复现（acceptance③）


def test_serialisation_is_byte_identical_twice() -> None:
    """同一批标注两次落盘**逐字节一致**：固定键序、固定编码、固定行尾。"""
    rows = [Annotation(item_id="a", kind="relevance", payload={"cluster": "x"},
                       label="relevant", note="", judge="deepseek-chat",
                       judged_at=NOW, rubric_sha="x" * 64)]

    assert to_jsonl(rows) == to_jsonl(rows)
    assert to_jsonl(rows).endswith("\n")
    assert "\r" not in to_jsonl(rows)


def test_two_rounds_that_differ_are_reported_item_by_item() -> None:
    """两轮不一致要**逐条报出来**，NEVER 让后一轮静默覆盖前一轮。

    静默覆盖会让「模型这次判得不一样」看起来像「一直就是这样」。
    """
    first = [Annotation("a", "relevance", {}, "relevant", "", "d", NOW, "s"),
             Annotation("b", "relevance", {}, "irrelevant", "", "d", NOW, "s")]
    second = [Annotation("a", "relevance", {}, "irrelevant", "", "d", NOW, "s"),
              Annotation("b", "relevance", {}, "irrelevant", "", "d", NOW, "s")]

    changed = diff_rounds(first, second)

    assert [c["item_id"] for c in changed] == ["a"]
    assert changed[0]["before"] == "relevant" and changed[0]["after"] == "irrelevant"


def test_identical_rounds_report_no_change() -> None:
    """阴性对照：两轮一样时**不报**——每轮都报等于没报。"""
    rows = [Annotation("a", "relevance", {}, "relevant", "", "d", NOW, "s")]

    assert diff_rounds(rows, rows) == []


def test_an_item_only_in_one_round_is_reported_too() -> None:
    """只在一轮里出现的条目也要报：**样本集变了**比标签变了更要紧。"""
    first = [Annotation("a", "relevance", {}, "relevant", "", "d", NOW, "s")]
    second = [Annotation("b", "relevance", {}, "relevant", "", "d", NOW, "s")]

    reported = {c["item_id"] for c in diff_rounds(first, second)}

    assert reported == {"a", "b"}


# ───────────────────────── 四、NEVER 调阈值（acceptance④）


def test_the_module_holds_no_threshold_constant() -> None:
    """本卡只产出标注。模块里**一个阈值字面量都没有**——判据钉在 AST 上。

    内置了阈值，标出来的金标就带着当前阈值的偏见；
    用它去调那个阈值，等于拿答案去验算答案。
    """
    from harness import gold_annotate

    tree = ast.parse(inspect.getsource(gold_annotate))
    floats = {
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, float)
    }

    assert floats == set(), f"模块里出现了浮点常量（像阈值）：{sorted(floats)}"


def test_the_module_never_writes_a_threshold_file() -> None:
    """也不许去写任何配置：调参是 CAL-02 的动作，本卡连写的路径都不该有。"""
    from harness import gold_annotate

    code = "\n".join(
        line for line in inspect.getsource(gold_annotate).splitlines()
        if not line.strip().startswith("#")
    )

    for forbidden in ("FLINT_Z_LINE", "THETA_REL", "load_tuning", "TUNING_KEYS"):
        assert forbidden not in code, f"模块碰了调参通道：{forbidden}"


# ───────────────────────── 五、产出的金标集（acceptance①）


def _goldset(name: str) -> list[dict]:
    path = GOLDSETS / f"{name}.jsonl"
    if not path.exists():
        pytest.skip(f"本机没跑过标注：缺 {path.name}（跑法见 trace）")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


@pytest.mark.parametrize("kind", KINDS)
def test_the_goldset_labels_are_all_in_the_closed_set(kind: str) -> None:
    """落盘的标签全在闭集里（含 `null` = 未标注）。"""
    allowed = set(LABELS[kind]) | {None}
    bad = {row["label"] for row in _goldset(kind)} - allowed

    assert bad == set(), f"{kind} 出现越界标签：{bad}"


def test_the_lineage_goldset_has_at_least_fifty_clusters() -> None:
    """acceptance①：血缘那一类**≥50 簇**——少于 50 的话这条断言本身没有意义。"""
    clusters = {row["payload"]["cluster_id"] for row in _goldset("lineage")}

    assert len(clusters) >= 50, f"只有 {len(clusters)} 簇"


@pytest.mark.parametrize("kind", KINDS)
def test_every_row_carries_its_provenance(kind: str) -> None:
    """每行都带判官/时间/判准指纹——**没有出处的标注不能拿去调参**。"""
    for row in _goldset(kind):
        assert row["judge"] and row["judged_at"] and len(row["rubric_sha"]) == 64


@pytest.mark.parametrize("kind", KINDS)
def test_the_stored_rubric_matches_the_one_in_force(kind: str) -> None:
    """每行记的判准指纹 = **当前判准**的指纹。

    对不上就说明判准改过而这批标注没重标——那批标注仍在盘上、看起来仍然有效，
    实际是按一套已经不存在的判准做的。
    """
    current = rubric_fingerprint(kind)
    stale = {row["rubric_sha"] for row in _goldset(kind)} - {current}

    assert stale == set(), f"{kind} 的标注按旧判准做（指纹 {stale}），判准已改：重标或回滚"


@pytest.mark.parametrize("kind", KINDS)
def test_every_row_carries_what_was_annotated(kind: str) -> None:
    """每行自带**被标的是什么**。

    只存 `item_id` 的话，CAL-02 拿到这批金标还得回头重跑一次抽样脚本才知道
    每条标的是什么对——而那次重跑与这次是不是同一批，谁也说不准。
    """
    for row in _goldset(kind):
        assert isinstance(row["payload"], dict) and row["payload"], row["item_id"]


def test_the_sampling_method_is_written_down() -> None:
    """样本**怎么挑的**要落盘：不写的话这批金标复现不了，只能重挑一次。"""
    manifest = GOLDSETS / "manifest.json"
    if not manifest.exists():
        pytest.skip("本机没跑过标注：缺 manifest.json")
    payload = json.loads(manifest.read_text(encoding="utf-8"))

    for kind in KINDS:
        entry = payload["kinds"][kind]
        assert len(entry["sampling"]) >= 20, f"{kind} 没写清怎么挑的样本"
        assert entry["source"], f"{kind} 没写样本从哪来"
