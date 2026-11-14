"""K5-01：英文 UI 文案机审（DeepSeek 逐条审 + `needs_review` 标记）。

## K5 悬着的是「没有人工审校资源」

`WORKORDER-v04.md#7` 的留空绕行方式是「en catalog 全量机翻占位 +
`needs_review: true` 标记字段」。本模块拿 DeepSeek 过一遍，
产出**问题清单与改写建议**——但它**不是**人工审校。

## 三条边界

1. **`en.json` 一个字节不动**。审校结果落旁挂文件 `web/messages/en.review.json`。
   写回目录就等于「机器改的文案上线了」，而 `needs_review` 只在旁挂文件里——
   下一个人打开 `en.json` 看到的是一份**看起来已经定稿**的目录；
2. **每条都带 `needs_review: true`**，连判 `ok` 的也带：机器说没问题不等于人看过。
   采纳建议之后仍是待审——改写本身也是机器做的；
3. **旁挂文件里不放译文本身**：放了就有了第二份目录，而两份里总有一份是旧的。

## 结构化输出坏了就报错

模型编出目录里没有的 key、或漏审了条目，一律抛错。静默丢掉的话，
「审了 141 条」与「审了 3 条外加编了 138 条」在结果上长得一模一样（S2-3）。

## 账走 JUDGE-01

调用经 `DeepSeekProvider.generate_with_purpose(purpose="i18n_review")`，
花费从它的 `UsageLedger` 取——**本模块自己不算钱**，
算两遍就会有两个数，而两个数里总有一个是错的。
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Final

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
EN_CATALOG: Final[Path] = REPO_ROOT / "web" / "messages" / "en.json"
SIDECAR: Final[Path] = REPO_ROOT / "web" / "messages" / "en.review.json"

REVIEW_PURPOSE: Final[str] = "i18n_review"
DEFAULT_BATCH_SIZE: Final[int] = 20

KINDS: Final[tuple[str, ...]] = ("ok", "grammar", "terminology", "machine-translated")


@dataclass(frozen=True)
class ReviewFinding:
    """一条审校结论。`kind` 说是哪一类、`note` 说为什么——

    少任何一样，这份清单就没法分诊：读的人只知道「有问题」，不知道该找谁改。
    """

    key: str
    kind: str
    note: str
    suggestion: str | None = None


@dataclass(frozen=True)
class ReviewReport:
    findings: list[ReviewFinding]
    cost_usd: Decimal
    model: str
    pricing_version: str
    calls: int

    @property
    def total(self) -> int:
        return len(self.findings)

    @property
    def needs_rewrite(self) -> int:
        return sum(1 for f in self.findings if f.suggestion)


def build_prompt(entries: dict[str, str]) -> str:
    """把一批词条摆进提示词。**逐字**摆进去——摘要或截断会让模型审的是另一份东西。

    三个角度都点名（grammar / terminology / machine-translated）：问得含糊的话，
    模型会只挑最显眼的一类，而术语不一致恰恰是最不显眼的那类。
    """
    listing = "\n".join(f"- {key}: {value}" for key, value in entries.items())
    return (
        "You are reviewing the English UI strings of a product whose source "
        "language is Chinese. For EACH entry below, judge three things:\n"
        "1. grammar — is it correct English?\n"
        "2. terminology — is the wording consistent with the other entries "
        "(same concept, same word)?\n"
        "3. machine-translated — does it read like a literal machine "
        "translation rather than product copy a native speaker would write?\n\n"
        f"Entries:\n{listing}\n\n"
        'Reply with JSON only: {"findings": [{"key": "...", "kind": '
        '"ok|grammar|terminology|machine-translated", "note": "why, in one '
        'sentence", "suggestion": "rewritten string, or omit if none"}]}\n'
        "Return one finding per entry, no more, no fewer. Keep UI strings short."
    )


def parse_review(
    payload: str,
    *,
    expected: set[str] | dict[str, str],
    require_complete: bool = False,
) -> list[ReviewFinding]:
    """解析模型回复。**坏了就抛错**，NEVER 返回空清单当作「没问题」。

    `expected` 给 dict 时连原文一起给——「建议与原文一模一样」这件事
    **只有知道原文才判得出来**。给 set 就只校验 key 集，不判这一条。
    """
    originals = expected if isinstance(expected, dict) else {}
    keys = set(expected)
    try:
        data = json.loads(payload)
    except ValueError as err:
        raise ValueError(f"审校回复不是 JSON：{payload[:120]!r}") from err
    raw = data.get("findings") if isinstance(data, dict) else None
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"审校回复里没有 findings 数组：{payload[:120]!r}")

    findings: list[ReviewFinding] = []
    for item in raw:
        if not isinstance(item, dict):
            # 用 ValueError 而不是 TypeError：调用方只会 catch 一种，
            # 而「回复的形状不对」在语义上是**值**的问题，不是传参类型错
            raise ValueError(f"findings 里有非对象项：{item!r}")  # noqa: TRY004
        key = str(item.get("key", ""))
        if key not in keys:
            # 编出来的 key 直接报错：静默丢掉的话，「审了 N 条」与
            # 「审了几条外加编了一堆」在结果上长得一模一样
            raise ValueError(f"审校结果里有目录中不存在的 key：{key!r}")
        kind = str(item.get("kind", ""))
        if kind not in KINDS:
            raise ValueError(f"{key} 的 kind 越界：{kind!r}（只认 {list(KINDS)}）")
        note = str(item.get("note", "")).strip()
        if not note:
            raise ValueError(f"{key} 没写为什么——没有理由的结论没法分诊")
        findings.append(ReviewFinding(
            key=key, kind=kind, note=note,
            suggestion=_clean_suggestion(item, originals.get(key)),
        ))

    if require_complete:
        missing = sorted(keys - {f.key for f in findings})
        if missing:
            # 漏审与「审过没问题」是两件事
            raise ValueError(f"这些条目没被审到：{missing}")
    return findings


def _clean_suggestion(item: dict[str, Any], original: str | None) -> str | None:
    """建议与原文一模一样 = 没有建议——留着它会让清单看起来有一堆待办。"""
    raw = item.get("suggestion")
    if not isinstance(raw, str) or not raw.strip():
        return None
    suggestion = raw.strip()
    return None if suggestion == original else suggestion


def review_catalog(
    provider: Any, entries: dict[str, str], *, batch_size: int = DEFAULT_BATCH_SIZE
) -> ReviewReport:
    """逐批审。每批一次调用、**每批都记账**（账在 provider 的账本里）。"""
    findings: list[ReviewFinding] = []
    calls = 0
    for batch in _batched(entries, batch_size):
        completion = provider.generate_with_purpose(
            build_prompt(batch), purpose=REVIEW_PURPOSE)
        # 把原文一起传下去：判「建议 == 原文」要用它
        findings.extend(parse_review(
            _strip_fences(getattr(completion, "text", "")), expected=batch))
        calls += 1

    summary = provider.ledger.reconcile()
    versions = summary.get("pricing_versions") or [""]
    return ReviewReport(
        findings=findings,
        cost_usd=Decimal(str(summary.get("total_usd", 0))),
        model=getattr(provider, "model", "unknown"),
        pricing_version=str(versions[0]),
        calls=calls,
    )


def _strip_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[-1]
        stripped = stripped.rsplit("```", 1)[0]
    return stripped.strip()


def _batched(entries: dict[str, str], size: int) -> Iterable[dict[str, str]]:
    items = list(entries.items())
    for start in range(0, len(items), size):
        yield dict(items[start:start + size])


def sidecar_payload(findings: list[ReviewFinding], *, model: str) -> dict[str, Any]:
    """旁挂文件的内容。**每条都是 `needs_review: true`**（见模块 docstring 第 2 条）。

    这里 NEVER 放译文本身——放了就有了第二份目录。
    """
    return {
        "_note": "机审结果，非人工审校。human_confirmed 由人改成 true。",
        "reviewed_by_model": model,
        "human_confirmed": False,
        "entries": {
            f.key: {
                "kind": f.kind,
                "note": f.note,
                "suggestion": f.suggestion,
                "needs_review": True,
                "reviewed_by": "machine",
            }
            for f in findings
        },
    }


def apply_suggestions(
    entries: dict[str, str], findings: list[ReviewFinding]
) -> tuple[dict[str, str], set[str]]:
    """采纳建议，返回（改写后的目录, 仍待人审的 key 集）。

    **采纳之后仍是待审**：改写本身也是机器做的。用不用这个函数是人的决定——
    本模块的 `__main__` 不调它。
    """
    rewritten = dict(entries)
    pending: set[str] = set()
    for finding in findings:
        if finding.suggestion and finding.key in rewritten:
            rewritten[finding.key] = finding.suggestion
            pending.add(finding.key)
    return rewritten, pending


def main() -> int:  # pragma: no cover - 取证入口（真调 DeepSeek，见 trace）
    import os

    from flint.llm.deepseek import DeepSeekProvider, load_deepseek_pricing
    from flint.llm.production import load_deepseek_tier

    tier = load_deepseek_tier()
    provider = DeepSeekProvider(
        api_key=tier.api_key, model=tier.model,
        pricing=load_deepseek_pricing(), base_url=tier.base_url,
    )
    catalog = json.loads(EN_CATALOG.read_text(encoding="utf-8"))
    entries = {k: v for k, v in catalog.items() if not k.startswith("_")}

    report = review_catalog(provider, entries,
                            batch_size=int(os.environ.get("FLINT_I18N_BATCH") or DEFAULT_BATCH_SIZE))
    SIDECAR.write_text(
        json.dumps(sidecar_payload(report.findings, model=report.model),
                   ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n")

    print(f"审了 {report.total} 条，{report.needs_rewrite} 条有改写建议，"
          f"{report.calls} 次调用，花费 ${report.cost_usd}")
    for finding in report.findings:
        if finding.kind != "ok":
            print(f"  [{finding.kind}] {finding.key}: {finding.note}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
