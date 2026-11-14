"""CAL-01：金标集标注（DeepSeek 代判 θ_rel / δ / 血缘）。

## 只标注，不调参

θ_rel、δ、血缘线都是 `CLAUDE.md#S4` 的未决项，**调参是 CAL-02**。
本模块里因此**一个阈值常量都没有**（有 AST 断言扫着）：内置了阈值，
标出来的金标就带着当前阈值的偏见，用它去调那个阈值，等于
**拿答案去验算答案**（`harness/gold_collect.py` 的原话）。

## 判准先落盘，再标注

`annotate()` 会先核盘上的判准文件与内置判准的指纹是否一致，对不上直接抛错。
「判准写在提示词里」与「判准落了盘」是两件事：前者跑完就没了，
后者是下一个人复核这批标注的唯一依据。

## 可复现的两半

1. **序列化确定**：固定键序 + `ensure_ascii=False` + `\\n` 行尾 → 同一批两次落盘逐字节一致；
2. **两轮差异逐条报出**（`diff_rounds`），后一轮 NEVER 静默覆盖前一轮——
   静默覆盖会让「模型这次判得不一样」看起来像「一直就是这样」。

## 标签是闭集

越界标签与坏判词一律记 `None`（未标注），**NEVER 挑一个最像的顶上**：
顶上去的那条会以一条正常数据的样子进入调参。
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Final

KINDS: Final[tuple[str, ...]] = ("relevance", "same_topic", "lineage")

LABELS: Final[dict[str, tuple[str, ...]]] = {
    "relevance": ("relevant", "irrelevant"),
    "same_topic": ("same", "different"),
    "lineage": ("correct", "wrong"),
}

RUBRICS: Final[dict[str, str]] = {
    "relevance": (
        "# 判准 · relevance（θ_rel 的标注面）\n\n"
        "问的是：**这条候选文本与这个簇讲的是同一件事吗**。\n\n"
        "- `relevant`：候选与簇名指向同一个具体对象、技术或事件；\n"
        "  同义词、上下位词（「农业机器人」与「果园采摘机械臂」）算相关。\n"
        "- `irrelevant`：只共享一个宽泛领域（都属「AI」「制造业」）不算相关——\n"
        "  按宽泛领域算相关，θ_rel 会被标成一个几乎恒真的判据。\n\n"
        "**拿不准时选 `irrelevant`**：把不确定算成相关，会让相关率虚高，\n"
        "而调参时读到的是「阈值再低一点也没事」。\n"
    ),
    "same_topic": (
        "# 判准 · same_topic（δ 的标注面）\n\n"
        "问的是：**这两条讲的是不是同一个主题**（能不能并成一条热点）。\n\n"
        "- `same`：同一事件/同一技术方向的两种说法，合并后不会丢信息；\n"
        "- `different`：属同一领域但各自成立（「液冷调度」与「模型压缩」）。\n\n"
        "**判的是主题，不是措辞**：两句话用词不同但指同一件事，算 `same`。\n"
        "**拿不准时选 `different`**：并错了两个主题，下游会把两条热点的证据混在一起，\n"
        "而那种错在产物上看不出来。\n"
    ),
    "lineage": (
        "# 判准 · lineage（血缘的标注面）\n\n"
        "问的是：**系统给出的这条血缘事件判对了吗**。\n\n"
        "`continued` 表示系统认为这个簇从前一天延续了下来；`new` 表示它是当天新出现的。\n"
        "给的是同一个簇在**今天**与**前一天**各自挂着的关键词：\n\n"
        "- `correct`：\n"
        "  · 判 `continued` 且两天的关键词指同一件事（措辞变化不算漂移）；\n"
        "  · 判 `new` 且前一天这个簇不存在。\n"
        "- `wrong`：\n"
        "  · 判 `continued` 但两天的关键词已经是两件事（簇漂移了，本该断开）；\n"
        "  · 判 `new` 但前一天这个簇就在（漏接了一条线）。\n\n"
        "**只判这一步对不对，NEVER 顺带评价簇名起得好不好**：\n"
        "那是另一件事，混进来会让这批标注同时在说两件事。\n"
    ),
}


class RubricNotOnDisk(Exception):
    """判准没落盘、或盘上的判准与内置的对不上——**先落盘再标注**。"""


@dataclass(frozen=True)
class AnnotationItem:
    item_id: str
    kind: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class Annotation:
    """一条标注。**判官 / 时间 / 判准指纹**三样缺一不可（见模块 docstring）。

    `payload` 也留在这里：**标注要自带被标的是什么**。只存 `item_id` 的话，
    CAL-02 拿到这批金标还得回头重跑一次抽样脚本才知道每条标的是什么对——
    而那次重跑与这次是不是同一批，谁也说不准。
    """

    item_id: str
    kind: str
    payload: dict[str, Any]
    label: str | None
    note: str
    judge: str
    judged_at: str
    rubric_sha: str


def rubric_fingerprint(kind: str) -> str:
    return hashlib.sha256(RUBRICS[kind].encode("utf-8")).hexdigest()


def write_rubrics(directory: Path) -> list[Path]:
    """把三份判准落盘。**每轮标注前先跑它**。"""
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for kind, text in RUBRICS.items():
        path = directory / f"{kind}.md"
        path.write_text(text, encoding="utf-8", newline="\n")
        written.append(path)
    return written


def _check_rubric_on_disk(kind: str, directory: Path) -> str:
    path = directory / f"{kind}.md"
    if not path.exists():
        raise RubricNotOnDisk(f"{kind} 的判准没落盘：{path}（先跑 write_rubrics）")
    on_disk = hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
    expected = rubric_fingerprint(kind)
    if on_disk != expected:
        raise RubricNotOnDisk(
            f"{kind} 盘上的判准与内置的对不上（盘 {on_disk[:12]}… / 内置 {expected[:12]}…）："
            "两轮标注会各按各的判准做，而记录上看起来是同一套"
        )
    return expected


def build_prompt(item: AnnotationItem) -> str:
    """判词 = 判准 + 被标的东西。缺任一，标注都无从复核。"""
    body = "\n".join(f"- {key}: {value}" for key, value in item.payload.items())
    allowed = " | ".join(LABELS[item.kind])
    return (
        f"{RUBRICS[item.kind]}\n"
        f"待标条目：\n{body}\n\n"
        f'只输出 JSON：{{"label": "{allowed}", "note": "一句话理由"}}'
    )


def parse_label(payload: str, *, kind: str) -> str | None:
    """解析标签。越界或坏判词一律 `None`（未标注），NEVER 顶一个最像的。"""
    text = payload.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        data = json.loads(text)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    label = data.get("label")
    return label if label in LABELS[kind] else None


def parse_note(payload: str) -> str:
    text = payload.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        data = json.loads(text)
    except ValueError:
        return ""
    return str(data.get("note") or "") if isinstance(data, dict) else ""


def annotate(
    provider: Any,
    items: list[AnnotationItem],
    *,
    rubric_dir: Path,
    now: Callable[[], str],
) -> list[Annotation]:
    """逐条标注。**判准必须已落盘**（否则抛错）。"""
    shas = {kind: _check_rubric_on_disk(kind, rubric_dir)
            for kind in sorted({i.kind for i in items})}
    out: list[Annotation] = []
    for item in items:
        completion = provider.generate_with_purpose(
            build_prompt(item), purpose=f"gold_annotate:{item.kind}")
        text = str(getattr(completion, "text", ""))
        out.append(Annotation(
            item_id=item.item_id, kind=item.kind, payload=dict(item.payload),
            label=parse_label(text, kind=item.kind), note=parse_note(text),
            judge=str(getattr(provider, "model", "unknown")),
            judged_at=now(), rubric_sha=shas[item.kind],
        ))
    return out


def to_jsonl(rows: list[Annotation]) -> str:
    """确定性序列化：固定键序、固定编码、固定行尾。两次落盘逐字节一致。"""
    return "".join(
        json.dumps(asdict(r), ensure_ascii=False, sort_keys=True) + "\n" for r in rows
    )


def diff_rounds(before: list[Annotation], after: list[Annotation]) -> list[dict[str, Any]]:
    """两轮之间**逐条**报差异。样本集变了也报——那比标签变了更要紧。"""
    lhs = {r.item_id: r for r in before}
    rhs = {r.item_id: r for r in after}
    changes: list[dict[str, Any]] = []
    for item_id in sorted(set(lhs) | set(rhs)):
        a = lhs.get(item_id)
        b = rhs.get(item_id)
        if a is not None and b is not None and a.label == b.label:
            continue
        changes.append({
            "item_id": item_id,
            "before": a.label if a is not None else "<不在这一轮>",
            "after": b.label if b is not None else "<不在这一轮>",
        })
    return changes
