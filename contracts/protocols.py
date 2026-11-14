"""燧石 Flint · 接口冻结件 (M0, 执行顺序 ③)

全部为 Protocol, 实现后置。同步 run() 一律废除, 长任务经 JobRunner [D4]。
免费/付费数据源、不同 LLM 均按同名协议热插拔; 单源故障自动降级不阻塞日更。
覆盖: M0 决策记录 + 审核 1~11 (v0.3.1) + 终轮补丁 (v0.3.2)。
冻结规则: 改动只能来自 ⑧ 对抗性推演产出的 v0.4 修订。
"""
from __future__ import annotations

from datetime import date
from typing import Literal, Protocol

from models import (
    Alignment, AnalysisContext, Block, Completion, DagReport,
    Dispute, Doc, EvidenceScore, FactDiff, FactsLedger, GapHint, JSON, Job,
    JobEvent, JobKind, PackageStatus, Principal,
    PricingRecord, Query, RevalidationTrigger, SectionSpec, TaskSpec, Topic,
    TopicSeed, TrendItem, UserEvidence, VerdictResult,
)

# ═════════════════════ 数据源 (六类, 统一溯源: source_id / url / fetched_at)


class TrendSource(Protocol):
    source_id: str

    def fetch_daily(self, day: date) -> list[TrendItem]: ...


class PaperSource(Protocol):
    def search(self, q: Query, since: date | None, limit: int) -> list[Doc]: ...


class PatentSource(Protocol):
    def search(self, q: Query, since: date | None, limit: int) -> list[Doc]: ...


class NewsSource(Protocol):
    def search(self, q: Query, since: date | None, limit: int) -> list[Doc]: ...


class CompetitorSource(Protocol):
    def search(self, q: Query, limit: int) -> list[Doc]: ...


class FundingSource(Protocol):
    """v1 实现返回空并标 not_available, 前端显示「信息不足 / 升级解锁」"""

    def search(self, company: str) -> list[Doc]: ...


class PricingParser(Protocol):
    """抓取原文 → 结构化定价; 低置信 → 前端「定价待确认」, 禁止无置信度数字 [B5]"""

    def parse(self, raw: str, url: str) -> list[PricingRecord]: ...


# ═════════════════════ 检索质量层 [B1~B4][D1-c][审7]


class QueryBuilder(Protocol):
    """四步: 术语标准化(中→英, 走映射表) → 同义/上下位扩展 → 多 query → 相关性评估"""

    def build(
        self,
        keywords: list[str],
        intent: Literal["support", "refute", "landscape"],
        locale: str,
    ) -> list[Query]: ...


class RelevanceJudge(Protocol):
    """< θ_rel → 改写重检(≤R 轮); 仍低才允许判「信息不足」— 区分"真没有"与"没搜对" """

    def hit_rate(self, q: Query, docs: list[Doc]) -> float: ...


class EvidenceScorer(Protocol):
    """双尺 [审7]: 按 doc.origin 选公式 (retrieved=B4 / user_provided=40·可核验+35·一手+25·时效);
    EvidenceScore.axis 回填判别; 跨类不比较分数, UI 分区展示。"""

    def strength(self, doc: Doc) -> EvidenceScore: ...


class CitationAligner(Protocol):
    """[D1-c] 两段式:
    stage="verdict": 判定前, 仅关键证据(上限 K); 未过 → 降 D
    stage="draft":   终稿前, 全量;   未过 → 去引用、Claim.confidence 降 speculative
    alignment_rate (红线 ≥0.95) 只统计 draft 段。
    """

    def align(
        self, claim: str, evidence: Doc, stage: Literal["verdict", "draft"]
    ) -> Alignment: ...


# ═════════════════════ LLM 调用层 [D9]


class LLMProvider(Protocol):
    def generate(self, prompt: str, tools: list[JSON] | None) -> Completion: ...

    def generate_structured(
        self, prompt: str, schema: JSON, max_retries: int
    ) -> JSON:
        """主路 tool use + 本方 schema 校验; 失败回填错误重试 ≤2;
        仍败按输出类型降级 (verdict→绝不猜测、判D并说明 / 章节→标缺口不阻塞)
        并记 GenerationRecord.structured_output_failures。"""
        ...


# ═════════════════════ 作业与渐进交付 [D4][D8][审6]


class JobRunner(Protocol):
    def submit(
        self,
        kind: JobKind,
        payload: JSON,
        budget: float,
        owner_scope: Principal,
        initiated_by: str,
    ) -> str: ...  # → job_id

    def cancel(self, job_id: str, actor_user_id: str) -> None:
        """[审6] 取消权 = initiated_by 本人, 或 owner_scope 内 role∈{owner,admin};
        越权 → 拒绝。阶段边界生效, 成本即时封顶。"""
        ...

    def get(self, job_id: str) -> Job: ...


class JobEventStream(Protocol):
    """SSE: JobEvent.seq 单调递增; 断线以 Last-Event-ID 调 replay 补发;
    重连流程 = 先 GET /jobs/{id} 取快照, 再续流。
    订阅权 [审6] = 取消权人群 + owner_scope 内 member 只读。"""

    def emit(self, event: JobEvent) -> None: ...

    def replay(self, job_id: str, after_seq: int) -> list[JobEvent]: ...


# ═════════════════════ 生成管线 (worker 内部步骤; 对外一律经 JobRunner)


class Analyzer(Protocol):
    def plan(self, seed: TopicSeed, topic: Topic, ctx: AnalysisContext) -> list[Query]: ...

    def verdict(self, evidence: list[Doc], ctx: AnalysisContext) -> VerdictResult: ...
    # 判定前须走 aligner stage="verdict"; 顺序 A>B>C>D 与四类硬规则见
    # VerdictResult docstring [D7][审1][审2]; 结构化输出失败绝不猜 verdict [D9]。


class ReportComposer(Protocol):
    def outline(self, project_id: str) -> list[str]: ...

    def freeze_ledger(self, deliverable_ids: list[str]) -> FactsLedger: ...
    # 提升不变量 (v0.3.2): 仅 confidence=="cited" 且 alignment=="supports" 的
    # claim 可提升为 Fact (origin="promoted_claim", 回填 source_claim_id /
    # promoted_from / Claim.promoted_fact_id); partial 不可提升。

    def draft_section(self, spec: SectionSpec, ledger: FactsLedger) -> list[Block]: ...
    # 各段只允许引用 ledger 中的 fact_id [B6]; status=="disputed" 的 fact 从
    # 可用池排除 [审10]; 涉我章节只经 ProfileRef、预算数字只经 PriceCell (v0.3.2)。

    def shrink(self, deliverable_id: str, section_id: str) -> list[Block]: ...

    def expand(
        self, deliverable_id: str, section_id: str
    ) -> list[Block] | list[GapHint]: ...
    # 无新证据 → 返回 GapHint (补录引导, 区分 missing_data / missing_permission
    # [审8]), 拒绝注水 [D13]。shrink/expand 与 regenerate 同守保护条件:
    # locked ∨ author=="user" ∨ user_modified 的 block 不得改写 (v0.3.2)。


class SpecExporter(Protocol):
    """audience 分叉 (v0.3.3): human_reader 路径保持独立 spec_export;
    ai_executor 路径下本能力并入 vibe_pack 的 S5~S7 章 (Task DAG /
    Context Manifest / Verification Harness), 不再单独产出 spec 交付物。"""

    def export(self, project_id: str) -> list[TaskSpec]: ...


class RegistryValidator(Protocol):
    """[E1] 依赖存在性: 查 PyPI/npm/crates; 不通过 → 替换并标 [replaced: 原因]"""

    def check(
        self, package: str, ecosystem: Literal["pypi", "npm", "crates"]
    ) -> PackageStatus: ...


class DagValidator(Protocol):
    """[T2] 无环 / inputs 溯源 / 孤儿与不可达检出。
    v0.3.3 增补: 双单位互斥必填校验 —— human_reader 任务须有 estimate_days(≤0.5);
    ai_executor 任务须有 estimate_cycles(≤2) 且 verify_cmd 非空;
    vibe_pack 质量门: verify 覆盖率=100%、context 超预算任务数=0。"""

    def validate(self, tasks: list[TaskSpec]) -> DagReport: ...


# ═════════════════════ 干预与复核 [D2][D6][审10][v0.3.2]


class InterventionService(Protocol):
    def lock(self, target_id: str, scope: Literal["block", "section"]) -> None: ...

    def regenerate_section(self, deliverable_id: str, section_id: str, guidance: str | None = None, block_id: str | None = None) -> str: ...
    # → job_id; 只动未受保护 block (locked ∨ author=="user" ∨ user_modified 原样
    # 保留); 产出新 GenerationRecord, Deliverable 版本+1。
    # guidance: 用户自然语言指令, 只引导生成方向, NEVER 当事实写入 (账本外事实经通道门拒稿);
    # block_id: 非 None → 块级 (仅重生成该块, 保护同节未选中兄弟块不动); None → 章节级。

    def inject_evidence(self, project_id: str, ev: UserEvidence) -> FactsLedger: ...
    # origin="user_provided"、access="private"; 走完整管道: 解析→双尺评分→对齐,
    # 不豁免任何校验; 默认不能单独支撑判 A (optin 见 GenerationRecord)。
    # 版本冲突 → 自动重放 ≤3 [审4]。

    def dispute(self, d: Dispute) -> FactsLedger: ...
    # 接受 → fact 标 disputed → 新生成排除、既有引用 block 标 advisory [审10];
    # 版本冲突 → 提示用户确认后重新提交 [审4]。


class Revalidator(Protocol):
    """[D6] 只检测不改状态; accept → ledger 派生(revalidation) → 同一 stale 机制。
    触发: scheduled(项目年龄阶梯) / user / event(簇 revival·momentum、refute 新强证据)。
    verdict_shift (v0.3.2): 必须内部提交完整 gate1_analysis 重跑规则表得出,
    VerdictShift.rerun_analysis_id 必填——不做启发式偏移, 系统内只有一套判定逻辑。
    版本冲突 → 整个 job 失效重跑 [审4]。"""

    def run(self, deliverable_id: str, trigger: RevalidationTrigger) -> str: ...  # → job_id

    def accept(self, report_id: str) -> FactsLedger: ...


# ═════════════════════ 存储与渲染 [D1-b][D3][F2][审4][审11]


class LedgerStore(Protocol):
    def derive(
        self,
        project_id: str,
        expected_parent_version: int,
        reason: Literal["initial", "inject_evidence", "dispute", "revalidation"],
        changes: JSON,
    ) -> FactsLedger:
        """乐观锁 [审4]: expected_parent_version 不匹配 →
        raise LedgerVersionConflict(current_version, current_facts)。
        冲突处置按来源分派 (见异常 docstring), 不做统一自动重试。"""
        ...

    def get(self, project_id: str, version: int) -> FactsLedger: ...

    def diff(self, project_id: str, v_from: int, v_to: int) -> FactDiff:
        """changed_fact_ids 机制: 只有引用变更 fact 的 block 标 needs_review;
        changed→advisory, removed→blocking, disputed→advisory [审11]。"""
        ...


class SnapshotStore(Protocol):
    """检索结果全量快照, 保留 180 天; 任何 Deliverable 可回放复现 [F2]。
    唯一例外: RedactionRecord (owner 删除权) [审9]。"""

    def put(self, payload: bytes) -> str: ...  # → snapshot_id

    def get(self, snapshot_id: str) -> bytes: ...


class Renderer(Protocol):
    """[D3] block 树为唯一真相; 渲染目标不回写。
    导出门禁 [审11]: blocking_reviews_open > 0 → 拒绝导出;
    private 证据导出强制标注「外部不可核验」且链接不外链 [审5]。"""

    def render(
        self,
        deliverable_id: str,
        fmt: Literal["markdown", "pdf", "docx", "html"],
    ) -> bytes: ...
