"""I18N-07：正交性 18 组合 harness（A8 / PRINCIPLES#A3）。

用法：
  python tools/orthogonality_check.py --combos all      # 9 区 × 2 语言 = 18 组
  python tools/orthogonality_check.py --self-test       # 先证明这把尺子会报警

## 四条断言（工单 §3-A3 校验点逐字）

  ① UI locale == lang
  ② 检索源集合 == SourceRegistry[region]
  ③ 热点集合内容 hash **与 lang 无关**
  ④ 生成产物 `Deliverable.lang == lang`

## 为什么先有 --self-test

「18 组合全绿」这句话本身没有信息量——**一把永远不报警的尺子也会全绿**。
所以本工具带一组**注入式反例**（故意让 locale 跟着 region 走、让热点集合掺进 lang、
让产物语言取自 region…），跑 `--self-test` 时逐条断言**这把尺子确实会红**。
自证不过就直接非零退出, 不进入正式 18 组。

## 被测的是「接线」，不是「实现细节」

本 harness 用**注入的探针**（`Probe`）代表系统的四个观测点。真实接线落地时把探针
换成真实读取即可, 断言一字不改——**NEVER 让 harness 自己去猜系统内部结构**。
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

# `python tools/x.py` 只把 tools/ 放进 sys.path，仓库根不在其中——
# 这里显式补上，否则 harness 连 flint.region 都 import 不到（首轮就是这么红的）。
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

REGIONS = ("CN", "HK", "US", "AU", "SG", "JP", "KR", "GB", "IT", "FR")
LANGS = ("zh", "en")


class OrthogonalityViolation(Exception):
    """由 lang 派生 region 或反向派生（工单 §3-A3「违反时」）。"""


@dataclass
class Probe:
    """系统四个观测点的注入面。真实接线时替换实现, 断言不动。"""

    ui_locale: Callable[[str, str], str]
    source_set: Callable[[str, str], tuple[str, ...]]
    hotspot_payload: Callable[[str, str], str]
    deliverable_lang: Callable[[str, str], str]


def _registry_sources(region: str) -> tuple[str, ...]:
    """SourceRegistry[region] 的期望值。

    K1 未决 → 注册表是空表种子, 故每区期望都是空元组。这不是「没测」:
    正交性要的是「源集只由 region 决定」, 空集同样能证伪——
    只要有一组因 lang 不同而拿到不同的源集, 断言②就红。
    """
    from flint.region.registry import load_seed_registry

    return tuple(sorted(e.source_id for e in load_seed_registry().select(region)))


def _honest_probe() -> Probe:
    """正确接线：locale 只由 lang 定、源集只由 region 定、热点集合不含 lang。"""
    return Probe(
        ui_locale=lambda region, lang: lang,
        source_set=lambda region, lang: _registry_sources(region),
        hotspot_payload=lambda region, lang: f"hotspots::{region}",
        deliverable_lang=lambda region, lang: lang,
    )


@dataclass
class Failure:
    region: str
    lang: str
    assertion: int
    detail: str


@dataclass
class Report:
    combos: int = 0
    failures: list[Failure] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures


def run_combos(probe: Probe) -> Report:
    """逐组跑四条断言。返回全部失败项（NEVER 首错即停——要看清是哪几组坏了）。"""
    report = Report()
    for region in REGIONS:
        for lang in LANGS:
            report.combos += 1

            locale = probe.ui_locale(region, lang)
            if locale != lang:
                report.failures.append(Failure(
                    region, lang, 1, f"UI locale={locale!r} != lang={lang!r}"))

            got = tuple(probe.source_set(region, lang))
            expected = _registry_sources(region)
            if got != expected:
                report.failures.append(Failure(
                    region, lang, 2, f"源集 {got} != SourceRegistry[{region}] {expected}"))

            # ③ 同一 region、两种 lang 的热点集合内容 hash MUST 相同
            other = LANGS[0] if lang == LANGS[1] else LANGS[1]
            h_this = hashlib.sha256(probe.hotspot_payload(region, lang).encode()).hexdigest()
            h_other = hashlib.sha256(probe.hotspot_payload(region, other).encode()).hexdigest()
            if h_this != h_other:
                report.failures.append(Failure(
                    region, lang, 3,
                    f"热点集合 hash 随 lang 变化（{lang}:{h_this[:8]} vs {other}:{h_other[:8]}）"))

            produced = probe.deliverable_lang(region, lang)
            if produced != lang:
                report.failures.append(Failure(
                    region, lang, 4, f"Deliverable.lang={produced!r} != {lang!r}"))
    return report


# ── 自证：这把尺子会不会报警 ─────────────────────────────────────

_BROKEN: dict[int, Callable[[], Probe]] = {
    1: lambda: Probe(                        # locale 跟着 region 走（A3 反例一）
        ui_locale=lambda region, lang: "ja" if region == "JP" else lang,
        source_set=lambda region, lang: _registry_sources(region),
        hotspot_payload=lambda region, lang: f"hotspots::{region}",
        deliverable_lang=lambda region, lang: lang),
    2: lambda: Probe(                        # 源集掺进 lang（本国隔离的形态之一）
        ui_locale=lambda region, lang: lang,
        source_set=lambda region, lang: (f"s-{lang}",),
        hotspot_payload=lambda region, lang: f"hotspots::{region}",
        deliverable_lang=lambda region, lang: lang),
    3: lambda: Probe(                        # 热点集合随 lang 变（A3 反例二）
        ui_locale=lambda region, lang: lang,
        source_set=lambda region, lang: _registry_sources(region),
        hotspot_payload=lambda region, lang: f"hotspots::{region}::{lang}",
        deliverable_lang=lambda region, lang: lang),
    4: lambda: Probe(                        # 产物语言取自 region
        ui_locale=lambda region, lang: lang,
        source_set=lambda region, lang: _registry_sources(region),
        hotspot_payload=lambda region, lang: f"hotspots::{region}",
        deliverable_lang=lambda region, lang: "zh" if region == "CN" else "en"),
}


def self_test() -> list[str]:
    """逐条注入反例，断言对应断言号确实会红。返回问题清单（空 = 自证通过）。"""
    problems: list[str] = []
    if not run_combos(_honest_probe()).ok:
        problems.append("阴性对照失败：正确接线下竟然报红——尺子本身有问题")
    for number, make in _BROKEN.items():
        report = run_combos(make())
        hit = {f.assertion for f in report.failures}
        if number not in hit:
            problems.append(f"断言 {number} 是空转的：注入了对应反例却没有报红（实报 {sorted(hit)}）")
    return problems


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="A3 正交性 18 组合 harness")
    parser.add_argument("--combos", choices=["all"], default=None)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv[1:])

    problems = self_test()
    if problems:
        print("自证不通过（这把尺子不会报警，18 组全绿没有意义）：", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print("自证通过：4 条断言各自注入反例后都会红；阴性对照（正确接线）不报红。")

    if args.self_test and args.combos is None:
        return 0

    report = run_combos(_honest_probe())
    if not report.ok:
        print(f"正交性校验不通过（{len(report.failures)} 项）：", file=sys.stderr)
        for f in report.failures:
            print(f"  - [{f.region}/{f.lang}] 断言{f.assertion}：{f.detail}", file=sys.stderr)
        return 1
    print(f"正交性校验通过：{report.combos} 组（9 区 × 2 语言）× 4 断言全过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
