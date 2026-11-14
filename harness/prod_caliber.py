"""生产口径验证跑批（M4-040/041 兑现，owner 裁决：免费档本地模型）。

- 每模型全链：12 金标场景（golddocs 12 样例 × 判例题材表）→ 逐节真实
  组稿（按模板 share 给字数靶）→ ①逐 check 问题语义作答（同一
  CHECK_ANSWER_LINE）→ ②渲染字量实测配比（同一 RATIO_DEVIATION_LINE）。
- 留痕：assets/prod_caliber/{model}.json（组稿全文 + 逐问答录 + 逐节
  配比录 + usage 实录）；HTTP 交换经 M1-008 RecordingTransport 录入
  fixtures/llm_local_runs/{model}/（CI 零联网不重跑本批，fixture 是
  运行出处）。
- 诚实口径：结果只对「具名本地模型」成立，NEVER 表述为付费档/Claude
  达标；对照表供 owner 定免费档默认模型。
运行：python -m harness.prod_caliber --model qwen3:30b
     （配置经 FLINT_LOCAL_* 环境变量，NEVER 硬编码）
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from collections.abc import Callable
from dataclasses import asdict
from datetime import date
from math import ceil
from pathlib import Path

import httpx

from eval.doc_metrics import TEMPLATES
from eval.heldout import HeldoutBank, load_heldout_bank
from eval.real_ratio import real_ratio_report, word_count
from eval.semantic_answers import (
    Composition,
    llm_answer_fn,
    semantic_answer_report,
)
from flint.compose.templates import load_template
from flint.domain.models import Ratio
from flint.llm.local import LocalProvider, LocalProviderUnavailable
from flint.llm.production import (
    AnthropicTier,
    LocalTier,
    ModelPricing,
    PaidTierProvider,
    load_anthropic_tier,
    load_local_tier,
)

# 组稿/判分 provider：免费档本地 LocalProvider 或付费档 PaidTierProvider
# （二者均有 .meter / .structured_output_failures / generate*）。
_Provider = LocalProvider | PaidTierProvider
from flint.testing.archive import archive_write
from flint.testing.replay import RecordedExchange, fixture_path, save_fixture

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "assets" / "prod_caliber"
FIXTURE_ROOT = REPO_ROOT / "fixtures"
RUN_DAY = date(2026, 7, 28)

# owner 裁决 1-2 @2026-07-28：1200 → 6000（对齐 doc_metrics 同尺度）。
# 1200 下 target=share×1200 而模板 min_words=share×3000，逐节靶恒为下限
# 的 40%——v3 两模型 68/68 words 节 100% 越界是构造必然而非模型行为。
SCALE_CHARS = 6000  # 每份组稿字量总靶（share × SCALE = 逐节靶）

JSONish = object  # 探针统计的宽松值类型（json.dumps 可序列化）

# owner @2026-07-29：与服务端 NUM_PARALLEL=1 对齐——单槽下模型逐个串行，
# 客户端 >1 只会让排队节请求把等待计入 600s 读超时（SCALE=6000 最坏排队
# ~735s>600s，拖垮整轮）；改 1 后吞吐不变（本就串行），消除排队超时风险。
CONCURRENCY = 1

# 12 金标场景题材表（golddoc 样例 × goldcases/trial 判例题材，确定性映射）
TOPICS: dict[str, str] = {
    "golddoc-generic-plain": "方言语音标注平台",
    "golddoc-generic-channels": "会议纪要摘要工具",
    "golddoc-thesis-plain": "量子传感地质勘探",
    "golddoc-thesis-channels": "车规芯片老化预测",
    "golddoc-startup-plain": "退役电池梯次检测",
    "golddoc-startup-channels": "户用储能电池",
    "golddoc-engineering-plain": "果园采摘执行器",
    "golddoc-engineering-channels": "仓储搬运机器人",
    "golddoc-grant-plain": "量子随机数云服务",
    "golddoc-grant-channels": "国产 EDA 插件市场",
    "golddoc-vibe_pack-plain": "行业术语纠错引擎",
    "golddoc-vibe_pack-channels": "方言语料授权分发",
}

# owner 裁决 2-1：组稿输入注入本节 check_questions **原文**（SectionSpec
# 设计即随节携带——M3-029 随节携带 / doc_metrics 组稿期复用；产品线组稿
# 器一定看得到它，不喂是人为缺陷）。原 _GUIDANCE_RULES 关键词表整表删除
# （子串误匹配 F-3 随之消失）；NEVER 改写/增强题面。
_SECTION_PROMPT = (
    "为「{topic}」项目计划书撰写「{section_id}」一节的正文（产品形态：）。\n"
    "本节的 check_questions（原文，随节规格携带）：\n"
    "{check_questions}\n"
    "- 凡出现数字，紧跟括号标注出处通道：事实数字用（Fact-n）、价格/"
    "预算/成本数字用（PriceCell-n）、涉及自身团队或资历的用（Profile-n）"
    "，n 为节内递增序号；\n"
    "- 正文字数 MUST 在 {lo} 到 {hi} 个汉字之间；\n"
    "- 只输出正文本身，不加标题、列表符号或任何说明。"
)


def _safe(model: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", model)


def load_samples() -> list[tuple[str, str]]:
    data = json.loads(
        (REPO_ROOT / "assets" / "golddocs" / "golddocs.json").read_text(
            encoding="utf-8"
        )
    )
    return [
        (str(s["sample_id"]), str(s["template_id"])) for s in data["samples"]
    ]


_REPAIR_PROMPT = (
    "以下是「{topic}」项目计划书「{section_id}」一节的草稿，正文 "
    "{actual} 个汉字，不符合要求（MUST 在 {lo} 到 {hi} 之间）。"
    "请改写到该区间：保留全部出处标注（Fact/PriceCell/Profile）与"
    "关键信息，只增删细节密度。只输出改写后的正文。\n草稿：\n{text}"
)

MAX_LENGTH_REPAIRS = 2  # 产品线 shrink/expand 同语义：量测后定向改写

# owner 裁决 @2026-07-29：max_tokens 右尺寸化——按本节最大字数 × 安全系数
# 封顶生成，替代平摊 16384（慢本地模型朝上限长跑 ~35 分是全量批时长隐患）。
# 安全系数覆盖 CJK 字→token 换算（暖态 gemma4:31b 实测 ~1.16 tok/字）与越界
# 头寸。只下调不上调：tokens 单位节（vibe_pack，max_words 以 token 计可达
# 16800）经上限收敛回原 16384，NEVER 因换算被截得比现状更短。
SECTION_MAX_TOKENS_SAFETY = 2.0
SECTION_MAX_TOKENS_CEILING = 16384  # 绝对上限 = 原平摊值：右尺寸只下调
SECTION_MAX_TOKENS_FLOOR = 256  # 极小节下限，防截断


def _section_max_tokens(ratio: Ratio) -> int:
    """按本节 max_words × 安全系数封顶生成 token（下限托底、上限=原 16384）。"""
    sized = ceil(ratio.max_words * SECTION_MAX_TOKENS_SAFETY)
    return min(SECTION_MAX_TOKENS_CEILING, max(SECTION_MAX_TOKENS_FLOOR, sized))

# owner 修复令步 3：正式组稿前一次性预热——丢弃调用把模型载入显存，给这一
# 步长超时吸收冷加载（KEEP_ALIVE=-1 保持热）；被测的每节调用仍用 600s 紧
# 超时（对停顿快失败）。预热用独立 client/provider，不入 fixture、不计量。
WARMUP_TIMEOUT = 1800.0


class ModelGenerationFailed(RuntimeError):
    """模型交白卷（空产两试即败）——对照表的合法结果，per-model 隔离捕获。"""


def _draft_nonempty(provider: _Provider, prompt: str, where: str) -> str:
    text = provider.generate(prompt, tools=None).text.strip()
    if not text:  # 空产 → 同预算重试一次；仍空即败（owner 铁律：不放宽）
        text = provider.generate(prompt, tools=None).text.strip()
    if not text:
        raise ModelGenerationFailed(
            f"{where}: empty generation twice (model {provider.model}) "
            "— model row recorded as failed, never fabricate"
        )
    return text


def repair_disabled_from_env(env: dict[str, str] | None = None) -> bool:
    """裁决 1-6：一次性开关（默认关 = 现状行为逐字一致）。"""
    source = env if env is not None else dict(os.environ)
    return source.get("FLINT_DISABLE_LENGTH_REPAIR") == "1"


def _warmup_model(
    base_url: str,
    model: str,
    api_key: str | None = None,
    http_client: httpx.Client | None = None,
) -> None:
    """一次性丢弃调用把模型载入显存（长超时吸收冷加载）。独立 client/
    provider——不入 fixture 录制、不进 usage 计量；结果丢弃。"""
    client = http_client or httpx.Client(timeout=WARMUP_TIMEOUT)
    try:
        provider = LocalProvider(
            base_url=base_url, model=model, http_client=client,
            api_key=api_key, max_tokens=1, disable_reasoning=True,
        )
        provider.generate("warmup", tools=None)  # 结果丢弃：只为载入显存
    finally:
        if http_client is None:
            client.close()


def compose_sample(
    make_provider: Callable[[int], _Provider],
    sample_id: str,
    template_id: str,
    repair_enabled: bool = True,
) -> Composition:
    spec, sections_meta = load_template(TEMPLATES / f"{template_id}.yaml")
    questions_by_id = {s.section_id: s.check_questions for s in sections_meta}
    topic = TOPICS[sample_id]
    sections: dict[str, str] = {}
    for section_id, ratio in spec.sections:
        target = max(30, round(ratio.share * SCALE_CHARS))
        lo, hi = round(target * 0.93), round(target * 1.07)
        where = f"{sample_id}/{section_id}"
        # 右尺寸化：本节生成 token 上限按本节 max_words × 安全系数封顶
        provider = make_provider(_section_max_tokens(ratio))
        verbatim = "\n".join(
            f"  {i}. {q}"
            for i, q in enumerate(questions_by_id.get(section_id, []), 1)
        ) or "  （本节无 check_questions）"
        prompt = _SECTION_PROMPT.format(
            topic=topic, section_id=section_id,
            check_questions=verbatim, lo=lo, hi=hi,
        )
        text = _draft_nonempty(provider, prompt, where)
        # 长度修复环（shrink/expand 产品机制的跑批镜像）：量测 → 定向
        # 改写 ≤2 轮；仍出带则留最接近靶的一版（度量器如实判）
        best = text
        rounds = MAX_LENGTH_REPAIRS if repair_enabled else 0
        for _round in range(rounds):
            count = word_count(best)
            if lo <= count <= hi:
                break
            repaired = _draft_nonempty(
                provider,
                _REPAIR_PROMPT.format(
                    topic=topic, section_id=section_id, actual=count,
                    lo=lo, hi=hi, text=best,
                ),
                where,
            )
            if abs(word_count(repaired) - target) < abs(count - target):
                best = repaired
        sections[section_id] = best
    return Composition(
        composition_id=sample_id, template_id=template_id, sections=sections
    )


def run_model(
    model: str,
    judged: bool,
    sample_limit: int | None = None,
    repair_enabled: bool | None = None,
    paid: bool = False,
) -> Path:
    if repair_enabled is None:
        repair_enabled = not repair_disabled_from_env()
    # 分档：免费档本地（load_local_tier）或付费档 Claude（load_anthropic_tier）。
    tier: LocalTier | None = None
    atier: AnthropicTier | None = None
    pricing: ModelPricing | None = None
    if paid:
        atier = load_anthropic_tier()
        model = atier.model  # FLINT_PAID_TIER_MODEL 为唯一真相
        pricing = ModelPricing(
            usd_per_mtok_input=atier.usd_per_mtok_input,
            usd_per_mtok_output=atier.usd_per_mtok_output,
        )
    else:
        tier = load_local_tier()
        if model not in tier.models:
            raise SystemExit(f"model {model!r} not in FLINT_LOCAL_MODELS")

    exchanges: list[RecordedExchange] = []

    class _Recorder(httpx.BaseTransport):
        def __init__(self) -> None:
            self._inner = httpx.HTTPTransport()

        def handle_request(self, request: httpx.Request) -> httpx.Response:
            response = self._inner.handle_request(request)
            body = response.read()
            exchanges.append(RecordedExchange(
                method=request.method, url=str(request.url),
                status_code=response.status_code,
                content_type=response.headers.get("content-type", ""),
                body_text=body.decode("utf-8"),
            ))
            return httpx.Response(
                response.status_code, headers=response.headers, content=body
            )

    shared_client = httpx.Client(transport=_Recorder(), timeout=600.0)

    def new_provider(max_tokens: int = SECTION_MAX_TOKENS_CEILING) -> (
        _Provider
    ):
        # 并发下每工作单元独立 provider 实例（计量互不竞态），共享同一
        # 录制 client（httpx.Client 线程安全；list.append 线程安全）。
        # max_tokens 右尺寸后逐节可变——组稿路径按本节 max_words 传入。
        if paid:
            # 付费档 Claude：组稿走 generate；判分走原生 output_config.format；
            # thinking 关（Sonnet 5 省略会自适应思考，显式关以控成本/防截断）。
            # NEVER 注入本地录制传输层——付费档用 anthropic 默认 client
            # （连接池/trust_env 健壮；录制传输层是本地档 CI 回放机制，付费档
            # 不入 CI，共享裸传输层跨数百 client 实例会连接失稳，实测报连接错误）。
            assert atier is not None and pricing is not None
            return PaidTierProvider(
                api_key=atier.api_key, model=model, pricing=pricing,
                max_tokens=max_tokens, disable_thinking=True,
            )
        # disable_reasoning=True（owner 裁决 @2026-07-29）：免费档本地推理
        # 模型关思考——推理耗预算/时间且裹坏结构化 JSON；组稿与判分同关。
        assert tier is not None
        return LocalProvider(
            base_url=tier.base_url, model=model, http_client=shared_client,
            api_key=tier.api_key, max_tokens=max_tokens,
            disable_reasoning=True,
        )

    providers: list[_Provider] = []
    answer_providers: list[_Provider] = []  # 指令 5：判分成本单列

    def tracked_provider(
        kind: str = "compose",
        max_tokens: int = SECTION_MAX_TOKENS_CEILING,
    ) -> _Provider:
        provider = new_provider(max_tokens)
        providers.append(provider)
        if kind == "answer":
            answer_providers.append(provider)
        return provider

    def compose_provider(max_tokens: int) -> _Provider:
        # 组稿逐节工厂：本节右尺寸后的 max_tokens 逐节实例化并计量
        return tracked_provider("compose", max_tokens)

    async def _compose_all(
        pairs: list[tuple[str, str]]
    ) -> list[Composition]:
        semaphore = asyncio.Semaphore(CONCURRENCY)

        async def one(sid: str, tid: str) -> Composition:
            async with semaphore:
                return await asyncio.to_thread(
                    compose_sample, compose_provider, sid, tid,
                    repair_enabled,
                )

        return list(await asyncio.gather(*(one(s, t) for s, t in pairs)))

    async def _answers_cache(
        compositions: list[Composition], bank: HeldoutBank,
    ) -> dict[tuple[str, str], tuple[bool, str]]:
        """并发预取逐问作答；度量器原样消费缓存回放（顺序语义与格式
        不变）。取题面 = held-out 题库（裁决 2-3）：题目 NEVER 来自模板
        或提示词——组稿输入（check_questions）与考核面自此分离。"""
        pairs: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for comp in compositions:
            _spec, section_specs = load_template(
                TEMPLATES / f"{comp.template_id}.yaml"
            )
            for section in section_specs:
                text = comp.sections.get(section.section_id, "")
                for heldout_q in bank.for_section(
                    comp.template_id, section.section_id
                ):
                    key = (heldout_q.q, text)
                    if key not in seen:
                        seen.add(key)
                        pairs.append(key)
        semaphore = asyncio.Semaphore(CONCURRENCY)

        async def one(question: str, text: str) -> tuple[bool, str]:
            async with semaphore:
                fn = llm_answer_fn(tracked_provider("answer"))
                return await asyncio.to_thread(fn, question, text)

        answers = await asyncio.gather(*(one(q, t) for q, t in pairs))
        return dict(zip(pairs, answers, strict=True))

    import time as _time

    # owner 修复令步 3：正式组稿前一次性预热（独立 client，长超时吸收冷
    # 加载）；不计入被测 wall。KEEP_ALIVE=-1 令模型保持热供后续紧超时调用。
    # 付费档 Claude 无冷加载，跳过预热。
    if not paid:
        assert tier is not None
        _warm_t0 = _time.time()
        _warmup_model(tier.base_url, model, api_key=tier.api_key)
        print(
            f"warmup {model} loaded in {_time.time() - _warm_t0:.1f}s",
            file=sys.stderr,
        )

    wall_start = _time.time()
    samples = load_samples()
    if sample_limit is not None and sample_limit < 12:
        # 探针路径（3-1/3-2 落账口径）：组稿指标专用——wall time /
        # 输出 token / 调用次数 / 逐节实际字量 / 是否落在模板 min~max；
        # 不作答、不进 N≥12 度量器、不落 trail
        t0 = _time.time()
        comps = asyncio.run(_compose_all(samples[:sample_limit]))
        t_compose = _time.time() - t0
        section_stats: dict[str, dict[str, JSONish]] = {}
        for comp in comps:
            spec, _meta = load_template(
                TEMPLATES / f"{comp.template_id}.yaml"
            )
            bounds = {sid: r for sid, r in spec.sections}
            section_stats[comp.composition_id] = {
                sid: {
                    "chars": word_count(text),
                    "min_words": bounds[sid].min_words,
                    "max_words": bounds[sid].max_words,
                    "in_bounds": (
                        bounds[sid].unit == "words"
                        and bounds[sid].min_words
                        <= word_count(text) <= bounds[sid].max_words
                    ),
                    "unit": bounds[sid].unit,
                }
                for sid, text in comp.sections.items()
            }
        print(json.dumps({
            "probe": True, "model": model, "concurrency": CONCURRENCY,
            "repair_enabled": repair_enabled,
            "wall_secs": round(t_compose, 1),
            "calls": sum(p.meter.calls for p in providers),
            "output_tokens": sum(p.meter.output_tokens for p in providers),
            "sections": section_stats,
        }, ensure_ascii=False))
        return OUT_DIR / "probe"
    bank = load_heldout_bank()
    if not any(bank.questions.values()):
        raise ModelGenerationFailed(
            "held-out bank empty (awaiting owner questions) — answer rate "
            "cannot be produced, run refused honestly"
        )
    compositions = asyncio.run(_compose_all(samples))
    cache = asyncio.run(_answers_cache(compositions, bank))

    def cached_answer(question: str, text: str) -> tuple[bool, str]:
        return cache[(question, text)]

    answer_report = semantic_answer_report(
        compositions, cached_answer, bank=bank
    )
    ratio_report = real_ratio_report(compositions)

    trail = {
        "model": model,
        "tier": "paid-anthropic" if paid else "free-local",
        # 口径如实落账（owner 任务）：付费档 thinking 关（disable_thinking=True）
        # / 判分原生 output_config.format；本地档 reasoning 关。两口径不可直接
        # 比较——对照分列不混同。
        "caliber": (
            "paid-anthropic: thinking=disabled, judge=output_config.format"
            if paid
            else "free-local: reasoning=disabled"
        ),
        "judged": judged,
        "status": "completed",  # 失败隔离新增态位：completed | failed_generation
        "run_day": RUN_DAY.isoformat(),
        "n_compositions": len(compositions),
        "scale_chars": SCALE_CHARS,
        "wall_seconds": round(_time.time() - wall_start, 1),
        "usage": {
            "calls": sum(p.meter.calls for p in providers),
            "input_tokens": sum(p.meter.input_tokens for p in providers),
            "output_tokens": sum(p.meter.output_tokens for p in providers),
            "cost_usd": sum(p.meter.cost_usd for p in providers),
        },
        "structured_output_failures": sum(
            p.structured_output_failures for p in providers
        ),
        "answer": {
            "bank_version": bank.bank_version,
            "questions": answer_report.questions,
            "answered": answer_report.answered,
            "rate": answer_report.rate,
            "verdict": answer_report.verdict,
            "records": [asdict(r) for r in answer_report.records],
        },
        # owner 指令 5：判分调用量（43 节 x3 题 x2 份/模板 = 258）成本单列
        "answer_usage": {
            "calls": sum(p.meter.calls for p in answer_providers),
            "output_tokens": sum(
                p.meter.output_tokens for p in answer_providers
            ),
        },
        "ratio": {
            "worst_deviation": ratio_report.worst_deviation,
            "meets_line": ratio_report.meets_line,
            "records": [asdict(r) for r in ratio_report.records],
        },
        "compositions": {
            c.composition_id: {
                "template_id": c.template_id,
                "sections": c.sections,
                "section_chars": {
                    sid: word_count(text) for sid, text in c.sections.items()
                },
            }
            for c in compositions
        },
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{_safe(model)}.json"
    # H-3 通用归档保护：同名 trail 若已存在且内容不同，先备份旧证据再写。
    archive_write(
        out_path, json.dumps(trail, ensure_ascii=False, indent=1)
    )
    # HTTP fixture 是本地档 CI 回放机制；付费档用默认 client（不录制），
    # 且付费档 NEVER 入 CI——trail JSON 即可复现记录，跳过空 fixture。
    if not paid:
        save_fixture(
            fixture_path(
                FIXTURE_ROOT, f"llm_local_runs/{_safe(model)}", RUN_DAY
            ),
            exchanges,
        )
    print(json.dumps({
        "model": model,
        "answer_rate": answer_report.rate,
        "answer_verdict": answer_report.verdict,
        "ratio_worst": ratio_report.worst_deviation,
        "ratio_meets_line": ratio_report.meets_line,
        "calls": sum(p.meter.calls for p in providers),
    }, ensure_ascii=False))
    return out_path


def _write_failure_trail(model: str, judged: bool, failure: str) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{_safe(model)}.json"
    # H-3 通用归档保护：失败行同样不覆盖已存在证据。
    archive_write(path, json.dumps({
        "model": model,
        "tier": "free-local",
        "judged": judged,
        "status": "failed_generation",
        "run_day": RUN_DAY.isoformat(),
        "failure": failure,
    }, ensure_ascii=False, indent=1))
    return path


def run_all(
    sample_limit: int | None = None,
    repair_enabled: bool | None = None,
) -> list[tuple[str, str]]:
    """per-model 失败隔离：单模型交白卷 = 对照表合法结果，链不中断。"""
    tier = load_local_tier()
    outcomes: list[tuple[str, str]] = []
    for model in tier.models:
        judged = model == tier.default_model
        try:
            run_model(model, judged=judged, sample_limit=sample_limit,
                      repair_enabled=repair_enabled)
            outcomes.append((model, "ok"))
        except (ModelGenerationFailed, LocalProviderUnavailable) as err:
            if sample_limit is None or sample_limit >= 12:
                _write_failure_trail(model, judged=judged, failure=str(err))
            outcomes.append((model, f"failed: {err}"))
            print(json.dumps(
                {"model": model, "status": "failed_generation",
                 "failure": str(err)}, ensure_ascii=False,
            ))
    if sample_limit is None or sample_limit >= 12:
        build_comparison()
    return outcomes


def build_comparison() -> Path:
    rows = []
    for path in sorted(OUT_DIR.glob("*.json")):
        if path.name == "comparison.json":
            continue
        trail = json.loads(path.read_text(encoding="utf-8"))
        if trail.get("status") == "failed_generation":
            rows.append({
                "model": trail["model"],
                "judged": trail["judged"],
                "status": "failed_generation",
                "failure": trail.get("failure", ""),
            })
            continue
        calls = trail["usage"]["calls"] or 1
        rows.append({
            "model": trail["model"],
            "judged": trail["judged"],
            "answer_rate": trail["answer"]["rate"],
            "answer_verdict": trail["answer"].get(
                "verdict",
                "meets_line" if trail["answer"].get("meets_line")
                else "below_old_line",
            ),
            "ratio_worst_deviation": trail["ratio"]["worst_deviation"],
            "ratio_meets_line": trail["ratio"]["meets_line"],
            "structured_output_failures": trail["structured_output_failures"],
            "output_tokens": trail["usage"]["output_tokens"],
            "avg_secs_per_call": round(
                trail.get("wall_seconds", 0) / calls, 1
            ),
        })
    (OUT_DIR / "comparison.json").write_text(
        json.dumps({"models": rows}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    lines = [
        "# 免费档本地模型四模型对照（生产口径双度量器 · 同一门槛）",
        "",
        (
            "| model | 档位角色 | 作答率 | 作答判定 | 配比最坏偏差 | ≤15% "
            "| 结构化失败 | 均次时延(s) |"
        ),
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        role = "判定跑（默认候选）" if row["judged"] else "report_only"
        if row.get("status") == "failed_generation":
            lines.append(
                f"| {row['model']} | {role} | 未能生成（空产两试即败） "
                "| ❌ | — | ❌ | — | — |"
            )
            continue
        lines.append(
            f"| {row['model']} | {role} | {row['answer_rate']:.3f} "
            f"| {row['answer_verdict']} "
            f"| {row['ratio_worst_deviation']:.3f} "
            f"| {'✅' if row['ratio_meets_line'] else '❌'} "
            f"| {row['structured_output_failures']} "
            f"| {row['avg_secs_per_call']} |"
        )
    lines += [
        "",
        (
            "结论只对上表具名本地模型成立（免费档口径）；付费档供应端的生产"
            "口径验证在该档启用时另行跑批关门。默认模型由 owner 依本表裁定。"
        ),
        "",
        (
            "**运行环境声明（裁决 1-7-①）**：v3 批次（qwen3:30b / "
            "gemma4:31b）产于服务端 OLLAMA_NUM_PARALLEL=1、KEEP_ALIVE=5m；"
            "qwen3.6:27b 冒烟起产于 NUM_PARALLEL=4 + KEEP_ALIVE=-1。两批"
            "运行环境不同——本表**时延维度跨批不可比**，仅达标/失败维度"
            "可对照。"
        ),
    ]
    md_path = OUT_DIR / "comparison.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="flint prod-caliber runner")
    parser.add_argument("--model", required=False)
    parser.add_argument("--judged", action="store_true")
    parser.add_argument("--samples", type=int, default=None)
    parser.add_argument("--comparison", action="store_true")
    parser.add_argument(
        "--all", action="store_true",
        help="全模型清单依次跑，per-model 失败隔离（判定跑 = 默认模型）",
    )
    parser.add_argument(
        "--no-length-repair", action="store_true",
        help="裁决 1-6 一次性开关：关闭长度修复环（默认开 = 现状行为）",
    )
    parser.add_argument(
        "--paid", action="store_true",
        help="付费档 Claude（load_anthropic_tier；model 取 FLINT_PAID_TIER_MODEL）",
    )
    args = parser.parse_args(argv)
    repair_enabled: bool | None = False if args.no_length_repair else None
    if args.comparison:
        print(build_comparison())
        return 0
    if args.all:
        outcomes = run_all(
            sample_limit=args.samples, repair_enabled=repair_enabled
        )
        print(json.dumps({"outcomes": outcomes}, ensure_ascii=False))
        return 0
    # 付费档 model 取自 FLINT_PAID_TIER_MODEL；--model 免费档必填。
    if not args.paid and not args.model:
        raise SystemExit("--model required (or --all / --comparison / --paid)")
    run_model(
        args.model or "", judged=args.judged, sample_limit=args.samples,
        repair_enabled=repair_enabled, paid=args.paid,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
