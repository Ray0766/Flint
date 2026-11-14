"""TS-011：combo 主题生成的模型口径跑批（owner @2026-07-31 授权两次跑）。

- combo 端到端：建 Origin（真实证据卡）→ TopicSeed → orchestrate_combo（TS-009：生成
  N 主题→[C1] 差异约束真跑→建 Project）。
- 免费档 qwen3.6（本地 OpenAI 兼容端点，load_local_tier / FLINT_LOCAL_*）经 M1-008
  HttpReplay 录制 → fixtures/topic_runs/{model}/combo.json；产出录 assets/topic_caliber/。
- 付费档 Claude（load_anthropic_tier / FLINT_ANTHROPIC_*）：环境变量未设 → STOP 报 owner
  去设，NEVER 在会话/代码里贴 key。
- 诚实口径：结果只对「具名模型」成立，NEVER 粉饰、NEVER 表述为普适达标。

运行（录制，需本地 qwen3.6 端点 + DB）：
  FLINT_LOCAL_BASE_URL=... FLINT_LOCAL_MODELS=qwen3.6:27b FLINT_FREE_TIER_MODEL=qwen3.6:27b \
  python -m harness.topic_caliber --mode record --model qwen3.6:27b
CI 回放（离线）：tests/topic/test_ts_011_replay.py 从 fixture 回放，零联网。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import anthropic
import httpx

from flint.domain.models import JSON, Origin, Principal, TopicSeed
from flint.embed import DeterministicHashBackend, EmbeddingService
from flint.llm.local import LocalProvider
from flint.llm.production import MeteredAnthropicProvider, ModelPricing
from flint.testing.replay import (
    HttpReplay,
    RecordedExchange,
    ReplayMiss,
    load_fixture,
    save_fixture,
)
from flint.topic.create import PgCardCatalog, create_origin, origin_to_seed
from flint.topic.orchestrate import ComboResult, orchestrate_combo

REPO = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO / "fixtures" / "topic_runs"
ASSET_ROOT = REPO / "assets" / "topic_caliber"
CORPUS_FILE = ASSET_ROOT / "card_corpus.json"

# 本模块对库**只读**：全文件零 INSERT/UPDATE/DELETE，只有 _pick_cross_cluster 的
# SELECT 与 PgCardCatalog（只读 evidence_cards / keywords）。所以它污染不了任何库。
# 它连的是 **demo 库**，理由不是习惯而是数据：replay_run 要按录制 asset 里的真实
# card_ids 还原 seed，而那些卡是真实抓取入库的行，只存在于 demo 库；空的 flint_test
# 里 create_origin 会直接 OriginValidationError("unknown card_ids")。
# 换言之这里的「正确的库」= 有那批真卡的库。要改指向就设 FLINT_CALIBER_DSN。
# ⚠ 代价（如实记账）：因此 `pytest -q` 仍会**读** demo 库——三条回放用例
#   （TS-011 / TS-014 / grounding）依赖 demo 里的真实证据卡。只读不写，不清数据。
DSN = os.environ.get(
    "FLINT_CALIBER_DSN",
    os.environ.get("FLINT_DEMO_DSN", "postgresql://flint:flint@localhost:55432/flint"),
)
DEFAULT_PROMPT = "topic_gen@1"
STRONG_PROMPT = "topic_gen@2"
# 固定输入（可复现）：一句话跨热点关联假设 + 目标主题数下界。
HYPOTHESIS = "把两个不同热点的方法迁移到同一落地场景，做一个可复用工作台"
TARGET = 5
NOW = datetime(2026, 7, 26, 12, 0, 0, tzinfo=UTC)


@dataclass
class RunConfig:
    model: str
    base_url: str


def fixture_file(model: str) -> Path:
    return FIXTURE_ROOT / model.replace(":", "_") / "combo.json"


async def _pick_cross_cluster(n: int) -> list[str]:
    import asyncpg

    conn = await asyncpg.connect(DSN)
    try:
        rows = await conn.fetch(
            "SELECT card_id, cluster_id FROM evidence_cards "
            "WHERE jsonb_array_length(keyword_ids) > 0 ORDER BY card_id")
    finally:
        await conn.close()
    picks: list[str] = []
    used: set[str] = set()
    for r in rows:
        cid = str(r["cluster_id"])
        if cid in used:
            continue
        used.add(cid)
        picks.append(str(r["card_id"]))
        if len(picks) == n:
            break
    return picks


async def build_seed(card_ids: list[str]) -> tuple[Origin, TopicSeed]:
    """真实证据卡 → combo Origin → TopicSeed（keywords 取卡的 canonical）。"""
    catalog = PgCardCatalog(dsn=DSN)
    owner = Principal(kind="user", id="caliber")
    origin = await create_origin(
        origin_id="origin-caliber", kind="combo", owner=owner,
        payload={"card_ids": card_ids, "hypothesis": HYPOTHESIS},
        created_at=NOW, catalog=catalog)
    seed = await origin_to_seed(seed_id="seed-caliber", origin=origin, catalog=catalog)
    return origin, seed


def _cards_context(card_ids: list[str]) -> str:
    """Phase 0.5 强接地：把被引卡真实内容+日期喂进 {cards} 占位。

    读 assets/topic_caliber/card_corpus.json（真机 PG 冻结）。@1 无 {cards} 占位、
    此串被忽略；@2 据此让模型能取真日期、知道卡里没有数字 → 从源头挡日期/数字幻觉。
    """
    if not CORPUS_FILE.exists():
        return "\n".join(sorted(card_ids))
    corpus = json.loads(CORPUS_FILE.read_text(encoding="utf-8"))
    lines: list[str] = []
    for cid in card_ids:
        entry = corpus.get(cid)
        if entry is None:
            lines.append(f'{cid} = （内容缺失）')
            continue
        texts = "；".join(str(t) for t in entry.get("texts", []))
        lines.append(f'{cid} = 「{texts}」（日期 {entry.get("day", "")}）')
    return "\n".join(lines)


def _id_factory() -> Any:
    counter = {"n": 0}

    def factory() -> tuple[str, str]:
        counter["n"] += 1
        return (f"topic-caliber-{counter['n']}", f"gr-caliber-{counter['n']}")

    return factory


def run_combo(
    provider: Any, seed: TopicSeed, card_ids: list[str], model: str
) -> ComboResult:
    """跑 orchestrate_combo（δ 真跑：delta=None 从嵌入空间估计）。"""
    embed = EmbeddingService(DeterministicHashBackend(dim=1024))
    return orchestrate_combo(
        provider, seed, embed, id_factory=_id_factory(),
        allowed_citation_ids=card_ids, model=model, job_id="job-caliber",
        ts=NOW, project_id="proj-caliber",
        owner=Principal(kind="user", id="caliber"), target=TARGET, delta=None)


def run_combo_batch(
    provider: Any, seed: TopicSeed, card_ids: list[str], model: str,
    *, target: int = TARGET, per_slot_retries: int = 2,
    prompt_name: str = DEFAULT_PROMPT, cards_context: str = "",
) -> tuple[ComboResult, int]:
    """崩溃容忍批生成（付费侧，省额度）：逐槽 generate_topic，单次结构化耗尽
    则重试 ≤per_slot_retries 后如实计 miss、跳过该槽（NEVER 猜、NEVER 硬造）；
    再 differentiate（identity 重生成——不再发付费调用，冲突诚实降级）。返
    (result, schema_misses)。差异约束仍真跑（δ=None）；产品 orchestrate_combo 的
    第三铁律（耗尽即 job failed）不变，本函数仅口径跑批的容错包装。
    """
    from flint.domain.models import GenerationRecord, Topic
    from flint.llm.structured import StructuredOutputExhausted
    from flint.topic.differentiate import differentiate
    from flint.topic.generate import generate_topic
    from flint.topic.project import build_project

    embed = EmbeddingService(DeterministicHashBackend(dim=1024))
    ids = _id_factory()
    records: list[GenerationRecord] = []
    topics: list[Topic] = []
    misses = 0
    while len(topics) < target:
        placed = False
        for _ in range(per_slot_retries + 1):
            topic_id, record_id = ids()
            try:
                topic, record = generate_topic(
                    provider, seed, topic_id=topic_id, job_id="job-caliber",
                    model=model, record_id=record_id, ts=NOW,
                    embed_service=embed, allowed_citation_ids=card_ids,
                    prompt_name=prompt_name, cards_context=cards_context)
            except StructuredOutputExhausted:
                misses += 1
                continue
            records.append(record)
            topics.append(topic)
            placed = True
            break
        if not placed:  # 该槽连试仍败 → 如实少出，不硬造
            break
    outcome = differentiate(topics, regenerate=lambda t: t, delta=None)
    project = build_project(
        project_id="proj-caliber",
        owner=Principal(kind="user", id="caliber"), origin_id=seed.origin_id,
        topic_ids=[t.topic_id for t in outcome.topics], created_at=NOW)
    return (
        ComboResult(topics=outcome.topics, records=records,
                    outcome=outcome, project=project),
        misses,
    )


def _serialize(result: ComboResult, card_ids: list[str], model: str) -> dict[str, Any]:
    return {
        "model": model,
        "card_ids": card_ids,
        "hypothesis": HYPOTHESIS,
        "delta": result.outcome.delta,
        "degraded": result.outcome.degraded,
        "dropped_conflicts": result.outcome.dropped_conflicts,
        "regen_rounds": result.outcome.regen_rounds,
        "generations": len(result.records),
        "topics": [
            {
                "topic_id": t.topic_id,
                "one_liner": t.one_liner,
                "target_user_tag": t.target_user_tag,
                "form_factor_tag": t.form_factor_tag,
                "why_now_claim": t.why_now.claim,
                "why_now_evidences": [
                    {"event": e.event, "event_date": e.event_date.isoformat(),
                     "citation_id": e.citation_id}
                    for e in t.why_now.evidences
                ],
                "speculative": t.why_now.speculative,
                "keyword_mapping": t.keyword_mapping,
            }
            for t in result.topics
        ],
    }


def _save_asset(record: dict[str, Any], model: str) -> None:
    ASSET_ROOT.mkdir(parents=True, exist_ok=True)
    (ASSET_ROOT / f"{model.replace(':', '_')}.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")


def record_run(config: RunConfig) -> dict[str, Any]:
    """录制模式：真机跑 qwen（免费本地），HTTP 交换落 fixture（M1-008）。"""
    card_ids = asyncio.run(_pick_cross_cluster(2))
    if len(card_ids) < 2:
        raise SystemExit("need >=2 distinct-cluster evidence cards in local PG")
    _origin, seed = asyncio.run(build_seed(card_ids))
    fixture = fixture_file(config.model)
    with HttpReplay(fixture, mode="record", live_transport=httpx.HTTPTransport()) as rp:
        provider = LocalProvider(
            base_url=config.base_url, model=config.model,
            http_client=rp.client(), disable_reasoning=True)
        result = run_combo(provider, seed, card_ids, config.model)
    record = _serialize(result, card_ids, config.model)
    record["pipeline"] = "orchestrate"
    _save_asset(record, config.model)
    return record


def record_local(
    model: str, base_url: str, prompt_name: str, label: str,
    *, disable_reasoning: bool = True, max_tokens: int = 4096,
    timeout: float = 600.0,
) -> dict[str, Any]:
    """本地 ollama 免费档一轮（Phase 1 本地天花板实测，零花费）。

    同 4 家 API 的崩溃容忍批（pipeline=batch），走 prompt_name（默认强接地 @2）+
    被引卡内容注入。用 `_RecordingTransport` + 显式 timeout（HttpReplay.client() 的
    httpx 默认 5s 对冷载/慢档不够；offload 重档更须长 timeout）——只录响应体，
    与付费侧一致、gzip 安全、可 ordered replay。label 决定落盘文件名——与既有
    qwen3.6:27b（orchestrate @1）资产分开，NEVER 覆盖。
    """
    card_ids = asyncio.run(_pick_cross_cluster(2))
    if len(card_ids) < 2:
        raise SystemExit("need >=2 distinct-cluster evidence cards in local PG")
    _origin, seed = asyncio.run(build_seed(card_ids))
    cards_ctx = _cards_context(card_ids)
    fixture = fixture_file(label)
    sink: list[RecordedExchange] = []
    client = httpx.Client(
        transport=_RecordingTransport(httpx.HTTPTransport(), sink), timeout=timeout)
    provider = LocalProvider(
        base_url=base_url, model=model, http_client=client,
        disable_reasoning=disable_reasoning, max_tokens=max_tokens)
    result, misses = run_combo_batch(
        provider, seed, card_ids, model,
        prompt_name=prompt_name, cards_context=cards_ctx)
    save_fixture(fixture, sink)
    record = _serialize(result, card_ids, model)
    record["cost_usd"] = 0.0                 # 本地免费档：实值 0（非占位）
    record["schema_misses"] = misses
    record["pipeline"] = "batch"
    record["prompt_name"] = prompt_name
    _save_asset(record, label)
    return record


def record_claude() -> dict[str, Any]:
    """付费档 Claude 一轮对比（owner @2026-07-31 授权，仅一轮）。

    load_anthropic_tier 读环境变量（未设 → ProviderWiringError 传播 = STOP，NEVER
    贴 key）；经模型无关 PaidTierProvider 跑同一 combo，HTTP 交换录 fixture。
    RecordingTransport 只录 method/url/响应体，**不录请求头 → x-api-key 不入 fixture**。
    key 仅用于构造 provider，NEVER 序列化/打印/落盘。
    """
    from flint.llm.production import load_anthropic_tier

    tier = load_anthropic_tier()  # 未设 env → ProviderWiringError（STOP，只列变量名）
    card_ids = asyncio.run(_pick_cross_cluster(2))
    if len(card_ids) < 2:
        raise SystemExit("need >=2 distinct-cluster evidence cards in local PG")
    _origin, seed = asyncio.run(build_seed(card_ids))
    fixture = fixture_file(tier.model)
    sink: list[RecordedExchange] = []
    # 压缩安全录制：M1-008 RecordingTransport 重包时留 content-encoding 头 →
    # 对 gzip 响应（Anthropic）二次解压报错。本 transport 录已解压 body、重包丢
    # content-encoding（仅录响应，请求头如 x-api-key NEVER 入 fixture）。
    client = httpx.Client(transport=_RecordingTransport(httpx.HTTPTransport(), sink))
    provider = _ClaudeToolProvider(
        api_key=tier.api_key, model=tier.model,
        pricing=ModelPricing(
            usd_per_mtok_input=tier.usd_per_mtok_input,
            usd_per_mtok_output=tier.usd_per_mtok_output),
        http_client=client, max_tokens=_CLAUDE_MAX_TOKENS)
    result, misses = run_combo_batch(provider, seed, card_ids, tier.model)
    cost = float(provider.meter.cost_usd)
    save_fixture(fixture, sink)  # 成功后落 fixture
    record = _serialize(result, card_ids, tier.model)
    record["cost_usd"] = round(cost, 4)  # 实录付费成本（小额、仅一轮）
    record["schema_misses"] = misses  # Claude tool-use 结构化未达次数（诚实计）
    record["pipeline"] = "batch"
    _save_asset(record, tier.model)
    return record


def record_cloud(vendor: str) -> dict[str, Any]:
    """通用云端档一轮对比（DeepSeek/GPT，owner @2026-07-31 授权，各仅一轮）。

    load_{vendor}_tier 读环境变量（未设 → ProviderWiringError 传播 = STOP，NEVER 贴
    key）；经模型无关 CloudOpenAIProvider（OpenAI 兼容 text-JSON 结构化）跑同一 combo，
    压缩安全录制（x-api-key NEVER 入 fixture）。崩溃容忍批（省额度、如实计 miss）。
    """
    from flint.llm.cloud import CloudOpenAIProvider
    from flint.llm.production import (
        ModelPricing,
        load_deepseek_tier,
        load_openai_tier,
    )

    loaders = {"deepseek": load_deepseek_tier, "openai": load_openai_tier}
    if vendor not in loaders:
        raise SystemExit(f"unknown cloud vendor {vendor!r} (want deepseek|openai)")
    tier = loaders[vendor]()  # 未设 env → ProviderWiringError（STOP，只列变量名）
    card_ids = asyncio.run(_pick_cross_cluster(2))
    if len(card_ids) < 2:
        raise SystemExit("need >=2 distinct-cluster evidence cards in local PG")
    _origin, seed = asyncio.run(build_seed(card_ids))
    fixture = fixture_file(tier.model)
    sink: list[RecordedExchange] = []
    # LocalProvider 仅给「默认 client」加 Authorization 头；注入 client 时须自带。
    # RecordingTransport 只录响应体 → Bearer 请求头 NEVER 入 fixture。
    client = httpx.Client(
        transport=_RecordingTransport(httpx.HTTPTransport(), sink),
        headers={"Authorization": f"Bearer {tier.api_key}"})
    provider = CloudOpenAIProvider(
        base_url=tier.base_url, model=tier.model, api_key=tier.api_key,
        pricing=ModelPricing(
            usd_per_mtok_input=tier.usd_per_mtok_input,
            usd_per_mtok_output=tier.usd_per_mtok_output),
        http_client=client, max_tokens=_CLAUDE_MAX_TOKENS)
    result, misses = run_combo_batch(provider, seed, card_ids, tier.model)
    cost = float(provider.meter.cost_usd)
    save_fixture(fixture, sink)
    record = _serialize(result, card_ids, tier.model)
    record["cost_usd"] = round(cost, 4)
    record["schema_misses"] = misses
    record["pipeline"] = "batch"
    _save_asset(record, tier.model)
    return record


_CLAUDE_MAX_TOKENS = 4096


class _ClaudeToolProvider(MeteredAnthropicProvider):
    """付费 Claude：tool-use 结构化路径（容开放 keyword_mapping）+ thinking 关。

    关 thinking = 省成本 + 防 max_tokens 预算被思考吃光导致 tool 输出截断
    （sonnet-5 省略 thinking 会自适应思考）。计量继承 MeteredAnthropicProvider。
    """

    def _call_once(
        self, prompt: str, tools: list[JSON] | None
    ) -> anthropic.types.Message:
        client = cast("Any", self._client)
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self._max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "thinking": {"type": "disabled"},
        }
        if tools is not None:
            kwargs["tools"] = tools
        message: anthropic.types.Message = client.messages.create(**kwargs)
        return message


class _RecordingTransport(httpx.BaseTransport):
    """压缩安全录制 transport：录已解压响应体、重包丢 content-encoding。

    只录 method/url/status/content-type/响应体——**请求头（含 x-api-key）NEVER 入
    fixture**。修 M1-008 RecordingTransport 对 gzip 响应二次解压的坑（不改共享件）。
    """

    def __init__(
        self, inner: httpx.BaseTransport, sink: list[RecordedExchange]
    ) -> None:
        self._inner = inner
        self._sink = sink

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        response = self._inner.handle_request(request)
        body = response.read()  # httpx 按 content-encoding 自动解压
        content_type = response.headers.get("content-type", "")
        self._sink.append(RecordedExchange(
            method=request.method, url=str(request.url),
            status_code=response.status_code, content_type=content_type,
            body_text=body.decode("utf-8")))
        headers = {"content-type": content_type} if content_type else None
        # 重包丢 content-encoding/content-length（body 已解压）
        return httpx.Response(response.status_code, headers=headers, content=body)


class _OrderedReplayTransport(httpx.BaseTransport):
    """按录制顺序回放交换（同 URL 多次调用忠实复现；零联网）。

    M1-008 HttpReplay 按 (method,url) 键路由——同 URL 多次调用会碰撞（末条胜）。
    主题生成是确定性顺序管线（gen1→gen2→…→regen），故按序回放即忠实复现。
    """

    def __init__(self, exchanges: list[Any]) -> None:
        self._exchanges = exchanges
        self._i = 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if self._i >= len(self._exchanges):
            raise ReplayMiss(f"replay exhausted at call #{self._i + 1}")
        ex = self._exchanges[self._i]
        self._i += 1
        headers = {"content-type": ex.content_type} if ex.content_type else None
        return httpx.Response(
            ex.status_code, content=ex.body_text.encode("utf-8"), headers=headers)


def _replay_provider(model: str, exchanges: list[Any]) -> Any:
    """按录制顺序回放的 provider——按 model 选类型（响应格式不同）。

    claude* → PaidTierProvider（anthropic 响应格式，api_key 回放不需真值）；
    否则 → LocalProvider（OpenAI 兼容格式）。均零联网（ordered transport）。
    """
    client = httpx.Client(transport=_OrderedReplayTransport(exchanges))
    if model.startswith("claude"):
        return _ClaudeToolProvider(
            api_key="replay-unused", model=model,
            pricing=ModelPricing(usd_per_mtok_input=0.0, usd_per_mtok_output=0.0),
            http_client=client, max_tokens=_CLAUDE_MAX_TOKENS)
    return LocalProvider(
        base_url="http://replay.invalid/v1", model=model,
        http_client=client, disable_reasoning=True)


def replay_run(label: str, base_url: str = "http://replay.invalid/v1") -> dict[str, Any]:
    """回放模式：按录制顺序回放 fixture，零联网（CI 用）。card_ids/model/prompt 取 asset。

    回放路径 MUST 与录制路径一致（否则调用次数不匹配 → ReplayMiss）：batch 侧录制走
    run_combo_batch（崩溃容忍），orchestrate 侧走 run_combo。label 索引落盘文件；provider
    类型按 asset["model"] 选（claude vs OpenAI 兼容）。cards_context 注入对 @1 是空操作。
    """
    asset = json.loads(
        (ASSET_ROOT / f"{label.replace(':', '_')}.json").read_text(encoding="utf-8"))
    model = str(asset.get("model", label))
    card_ids = list(asset["card_ids"])
    _origin, seed = asyncio.run(build_seed(card_ids))
    exchanges = load_fixture(fixture_file(label))
    provider = _replay_provider(model, exchanges)
    if asset.get("pipeline") == "batch":
        result, _misses = run_combo_batch(
            provider, seed, card_ids, model,
            prompt_name=str(asset.get("prompt_name", DEFAULT_PROMPT)),
            cards_context=_cards_context(card_ids))
    else:
        result = run_combo(provider, seed, card_ids, model)
    return _serialize(result, card_ids, model)


def _load_anthropic_or_stop() -> None:
    """付费档 Claude：环境变量未设 → STOP 报 owner（NEVER 贴 key）。"""
    from flint.llm.production import ProviderWiringError, load_anthropic_tier

    try:
        load_anthropic_tier()
    except ProviderWiringError as err:
        raise SystemExit(
            "STOP (owner action needed): Claude 对比档环境变量未设 —— "
            f"{err}. 请 owner 在运行环境设 FLINT_ANTHROPIC_API_KEY / "
            "FLINT_PAID_TIER_MODEL / FLINT_ANTHROPIC_USD_PER_MTOK_INPUT / _OUTPUT "
            "（NEVER 贴进会话或代码），设好后重跑 --model <claude-model>。"
        ) from err


def _check_cloud_or_stop() -> None:
    """两家云端档自检：任一未设 → STOP 报 owner（只列缺失变量名，NEVER 贴 key）。"""
    from flint.llm.production import (
        ProviderWiringError,
        load_deepseek_tier,
        load_openai_tier,
    )

    problems: list[str] = []
    for name, loader in (("deepseek", load_deepseek_tier), ("openai", load_openai_tier)):
        try:
            loader()
        except ProviderWiringError as err:
            problems.append(f"{name} → {err}")
    if problems:
        raise SystemExit(
            "STOP (owner action needed): 云端档环境变量未设 —— "
            + " | ".join(problems)
            + "。请 owner 在运行环境设对应 FLINT_DEEPSEEK_* / FLINT_OPENAI_*"
            "（NEVER 贴进会话或代码），设好后重跑 --mode record-cloud --vendor <家>。"
        )
    print("deepseek + openai tiers configured; safe to run cloud compare")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TS-011/014 topic caliber run")
    parser.add_argument(
        "--mode",
        choices=[
            "record", "record-claude", "record-cloud", "record-local",
            "replay", "check-claude", "check-cloud",
        ],
        default="record")
    parser.add_argument("--model", default="qwen3.6:27b")
    parser.add_argument("--vendor", choices=["deepseek", "openai"], default="deepseek")
    parser.add_argument("--base-url", default="http://localhost:11434/v1")
    parser.add_argument(
        "--prompt", default=STRONG_PROMPT,
        help="prompt 版本（本地跑默认强接地 topic_gen@2）")
    parser.add_argument(
        "--label", default="",
        help="落盘文件名（本地跑默认 {model}#{prompt尾号}，避免覆盖既有资产）")
    parser.add_argument(
        "--no-disable-reasoning", action="store_true",
        help="推理模型探针：保留思考（默认关思考省预算）")
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--timeout", type=float, default=600.0,
                        help="本地跑 httpx 超时秒（offload 重档调大）")
    args = parser.parse_args(argv)
    if args.mode == "check-claude":
        _load_anthropic_or_stop()
        print("anthropic tier configured; safe to run Claude compare")
        return 0
    if args.mode == "check-cloud":
        _check_cloud_or_stop()
        return 0
    if args.mode == "record":
        record = record_run(RunConfig(model=args.model, base_url=args.base_url))
    elif args.mode == "record-claude":
        record = record_claude()
    elif args.mode == "record-cloud":
        record = record_cloud(args.vendor)
    elif args.mode == "record-local":
        suffix = args.prompt.split("@")[-1]
        label = args.label or f"{args.model}#v{suffix}"
        record = record_local(
            args.model, args.base_url, args.prompt, label,
            disable_reasoning=not args.no_disable_reasoning,
            max_tokens=args.max_tokens, timeout=args.timeout)
    else:
        record = replay_run(args.label or args.model)
    print(json.dumps({k: record[k] for k in ("model", "generations", "degraded",
          "delta", "regen_rounds")}, ensure_ascii=False))
    print(f"topics: {len(record['topics'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
