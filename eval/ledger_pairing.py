"""台账成对性机械审计（M4-036 复审整改：纪律四犯后改为断言执法）。

- 规则：每个出现 verified / blocked / review_passed / review_failed 事件
  的**任务卡** task_id，全账内 MUST 存在至少一条 started 事件。
- 存在性而非位置序：append-only 台账允许 BACKFILL 后置（M2-023 判例），
  故不断言 started 行位置在前，只断言其存在——漏拍在下一次全量测试即
  爆红，人工检查表退役。
- 两类豁免（枚举封闭，NEVER 扩展新漏拍进来）：
  ① 里程碑生命周期记录（M?-expand / M3-CLOSE 形态，不匹配卡号
     `M\\d-\\d{3}`）——单事件设计，无 started 语义；
  ② 前判例期存量：started 成对惯例在 M3-037 返工后才成为落账规则，
     M1/M2 期 35 张卡的缺行是惯例前史，冻结为显式清单（首跑机械审计
     @2026-07-28 采集），不回填不再增。
- 常驻执法点：tests/m4/test_ledger_pairing.py 随全量 pytest 每轮跑；
  首跑即抓到 M4-039 漏拍（人工检查单四轮未见），机械化价值实证。
"""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

PAIRED_EVENTS = frozenset(
    {"verified", "blocked", "review_passed", "review_failed"}
)

_CARD_ID = re.compile(r"M\d-\d{3}\Z")

# 前判例期存量（M1/M2，惯例确立前；冻结清单，见模块 docstring ②）
PRE_CONVENTION_LEGACY = frozenset({
    "M1-004", "M1-005", "M1-006", "M1-008", "M1-009", "M1-010",
    "M1-011", "M1-012", "M1-013", "M1-014", "M1-016", "M1-017",
    "M1-018", "M1-019", "M1-020", "M1-021", "M1-022", "M1-023",
    "M1-024", "M1-025", "M1-026", "M1-027", "M1-028", "M1-031",
    "M2-006", "M2-010", "M2-011", "M2-012", "M2-013", "M2-018",
    "M2-019", "M2-021", "M2-022", "M2-025", "M2-026",
})


def load_ledger(path: Path) -> list[dict[str, object]]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


# ── ts 单调性执法（台账时间戳说明 review_passed @2026-07-28 后落码）──

EPOCH_TASK_ID = "LEDGER-TS-NOTE"  # 纪元锚：以 task_id 检索，NEVER 行号硬编码

_MACHINE_UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")


TS_FUTURE_TOLERANCE_SECONDS = 300  # 上界容差（时钟偏斜余量，明确声明）

# 已披露的估写超前异常行（冻结闭集，判例同 PRE_CONVENTION_LEGACY）：
# 第 457 行 ts 估写为 18:35 而真钟 ~18:12——上界断言当场抓获（作者自咬），
# 台账 458 行更正记录在案。该行从时钟链**整体跳过**（其伪值不得毒化
# 后续真实时间行）；NEVER 增补新条目——新的估写行为应当被抓红而非入册。
FORWARD_ESTIMATE_ANOMALIES: frozenset[tuple[str, str]] = frozenset(
    {("2026-07-28T18:35:00Z", "M4-040")}
)


def _parse_utc(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def ts_monotonicity_violations(
    entries: list[dict[str, object]],
    now: datetime | None = None,
) -> list[str]:
    """纪元锚（LEDGER-TS-NOTE 首现行）之后（1-5 加固版）：
    ① 格式：ts MUST 机器钟 UTC 形态——**任何行不豁免**（含 BACKFILL）；
    ② 上界：ts NEVER 晚于执行时机器钟 + TS_FUTURE_TOLERANCE_SECONDS
      （向前伪造/漂移即 205 行原病灶，正面拦截）；
    ③ 非递减：普通行 ts 对链非递减；
    ④ BACKFILL 豁免收紧：仅豁免 ts 非递减检查，且 MUST 同时携
      recorded_ts（机器钟补录时点）字段——recorded_ts 自身受格式/上界/
      对链非递减约束并接续时钟链；note 有 'BACKFILL' 子串但无
      recorded_ts 的行 NEVER 豁免。
    锚前历史不回溯（205 行日历漂移是已披露的既成事实）。"""
    epoch = next(
        (i for i, e in enumerate(entries)
         if str(e.get("task_id")) == EPOCH_TASK_ID),
        None,
    )
    if epoch is None:
        return []
    ceiling = (now if now is not None else datetime.now(UTC)) + timedelta(
        seconds=TS_FUTURE_TOLERANCE_SECONDS
    )
    violations: list[str] = []
    prev_clock = _parse_utc(str(entries[epoch]["ts"]))
    for offset, entry in enumerate(entries[epoch + 1:], start=epoch + 2):
        ts = str(entry.get("ts", ""))
        note = str(entry.get("note", ""))
        recorded_raw = entry.get("recorded_ts")
        if (ts, str(entry.get("task_id"))) in FORWARD_ESTIMATE_ANOMALIES:
            continue  # 已披露异常：跳过且不推进时钟链（见常量注释）
        if not _MACHINE_UTC.fullmatch(ts):
            violations.append(
                f"line {offset}: ts {ts!r} not machine-clock UTC form"
            )
            continue
        moment = _parse_utc(ts)
        if moment > ceiling:
            violations.append(
                f"line {offset}: ts {ts} in the future beyond machine clock "
                f"+ {TS_FUTURE_TOLERANCE_SECONDS}s tolerance"
            )
            continue
        if "BACKFILL" in note and recorded_raw is not None:
            recorded_s = str(recorded_raw)
            if not _MACHINE_UTC.fullmatch(recorded_s):
                violations.append(
                    f"line {offset}: recorded_ts {recorded_s!r} not "
                    "machine-clock UTC form"
                )
                continue
            recorded = _parse_utc(recorded_s)
            if recorded > ceiling:
                violations.append(
                    f"line {offset}: recorded_ts {recorded_s} in the future"
                )
            elif recorded < prev_clock:
                violations.append(
                    f"line {offset}: recorded_ts {recorded_s} backjumps the "
                    "clock chain (backfill recording moment must be monotone)"
                )
            else:
                prev_clock = recorded
            continue  # 仅 ts 非递减检查被豁免；格式/上界已查
        if moment < prev_clock:
            violations.append(
                f"line {offset}: ts {ts} < previous "
                f"{prev_clock.strftime('%Y-%m-%dT%H:%M:%SZ')} (non-BACKFILL "
                "backjump after epoch)"
            )
        else:
            prev_clock = moment
    return violations


def pairing_violations(entries: list[dict[str, object]]) -> list[str]:
    started = {
        str(e["task_id"]) for e in entries if e.get("event") == "started"
    }
    violations: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        task_id = str(entry["task_id"])
        event = str(entry.get("event"))
        if not _CARD_ID.fullmatch(task_id):
            continue  # 生命周期记录（expand/CLOSE）单事件设计
        if task_id in PRE_CONVENTION_LEGACY:
            continue
        if event in PAIRED_EVENTS and task_id not in started:
            key = f"{task_id}:{event}"
            if key not in seen:
                seen.add(key)
                violations.append(
                    f"{task_id}: {event} recorded but no started line in ledger"
                )
    return violations
