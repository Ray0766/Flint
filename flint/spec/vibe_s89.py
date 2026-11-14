"""vibe_pack S8/S9 章（M4-006，CLAUDE.md#S8/#S9 同构）。

- S8：progress.jsonl 事件约定（五事件、append-only）+ trace 规格 +
  新会话启动规则；S9：六停清单 + 审核 agent 五项检查单 + 人审节点。
- 同构性由 tests/m4/test_m4_006.py 对照本仓自用 CLAUDE.md 断言
  （双重狗粮：本仓按此规范被执行，生成包把同一规范交给下游）。
"""
from __future__ import annotations

from typing import Final

LEDGER_EVENTS: Final[tuple[str, ...]] = (
    "started", "verified", "review_passed", "review_failed", "blocked",
)

STOP_CONDITIONS: Final[tuple[str, ...]] = (
    "冻结件类型/签名不够用",
    "命中 S4 未决 Open Question 且无法绕开",
    "新依赖 registry 校验失败、或只有付费方案",
    "context 预算或 cycle 上限无法通过拆分满足",
    "同一原因连续 2 次 verify/review 失败",
    "任何不可逆操作触点",
)

REVIEW_CHECKLIST: Final[tuple[str, ...]] = (
    "测试真实覆盖 acceptance 语义（非 assert True / 非只测 happy path）",
    "无冻结件偏离（类型、签名、判别联合逐字比对）",
    "无禁用词",
    "trace 与 progress.jsonl 完整",
    "装载未超预算",
)

HUMAN_NODES: Final[tuple[str, ...]] = (
    "里程碑出口报告", "生产部署", "数据删除", "付费接口开通",
)


def build_s8() -> str:
    events = "|".join(LEDGER_EVENTS)
    return "\n".join(
        [
            "## S8 Progress Ledger（会话必死前提）",
            "",
            (
                "- `docs/progress.jsonl`（append-only，机器可读进度真相）"
                "——每行："
            ),
            (
                '  `{"ts","task_id","event":"' + events
                + '","cycles_used","note"}`'
            ),
            (
                "- `docs/trace/{task_id}.md`：实际装载清单（inputs 来源）"
                "+ 断点与决策日志 + 拆分/返工记录；"
            ),
            (
                "- **新会话启动 MUST**：读 `progress.jsonl` 末 20 行 → "
                "定位在跑/被阻任务 → 读对应 trace → 再动手。"
                "NEVER 依赖上一会话的记忆；NEVER 重做 event=verified "
                "之后的任务除非 review_failed。"
            ),
        ]
    )


def build_s9() -> str:
    lines = [
        "## S9 Escalation Rules",
        "",
        "**停下问 owner（写问题单并 blocked）**：",
    ]
    lines += [
        f"{i}. {cond}；" for i, cond in enumerate(STOP_CONDITIONS, start=1)
    ]
    lines += ["", "**审核 agent 检查单（review_gate 任务）**："]
    lines += [
        f"{mark} {item}；"
        for mark, item in zip("①②③④⑤", REVIEW_CHECKLIST, strict=True)
    ]
    lines += [
        "任一不过 → `review_failed` + 意见写入 trace，任务回 started。",
        "",
        f"**人审节点（owner 本人）**：{'、'.join(HUMAN_NODES)}。",
    ]
    return "\n".join(lines)
