"""边界 schema 与错误体（M2-041，技术方案 E3）。

- pydantic 只活在 flint/api/ 内（E1 分层：域层保持 dataclass，验收有全包
  扫描断言兜底）；域对象经 from_domain 显式换乘，不做隐式共享。
- 错误体 {code, message, detail?}：code 为机器可读枚举（Literal 收口），
  前端按 code 分支、message 给人读、detail 携带结构化上下文。
- JobView 是 GET /jobs/{id} 快照形（D8 断线重连第一步）；Principal 内部
  结构不过边界（审6 权限判定留在服务端）。
"""
from __future__ import annotations

from datetime import datetime
from typing import Final, Literal, get_args

from pydantic import BaseModel, ConfigDict

from flint.domain.models import JSON, Job

ErrorCode = Literal[
    "LEDGER_CONFLICT",
    "EXPORT_BLOCKED",
    "PERMISSION_DENIED",
    "BUDGET_EXCEEDED",
    "NOT_FOUND",
    "VALIDATION_FAILED",
    "SERVICE_UNAVAILABLE",
    # —— v0.4 增量（GRAPH-07 / 工单 §5-F 的 F7/F8）：空假设边被服务端独立拦下 ——
    # 单列一码而不是并进 VALIDATION_FAILED: 「边上没写假设」与「请求体格式不对」
    # 的修法完全不同，前端要据此把光标送回假设输入框而不是弹一句通用报错。
    "EMPTY_HYPOTHESIS",
    # —— AUTH-03：两种 401 分开报。两者都是「你是谁」的问题，但修法相反：
    # `IDENTITY_MISSING` 是**调用方漏了头**（改请求），
    # `IDENTITY_UNKNOWN` 是**这个 id 不是任何人**（换身份或去登记）。
    # 并成一个码的话，前端只能显示一句通用的「未认证」，而那两件事的下一步不同。
    # 与 `PERMISSION_DENIED`（403，你是谁没问题、你不能干这件事）三者互不覆盖。
    "IDENTITY_MISSING",
    "IDENTITY_UNKNOWN",
    # —— LOCK-01：project 行的乐观锁冲突（409）。
    # **NEVER 借 `LEDGER_CONFLICT`**：那一个说的是「这个项目的**事实账本**变了」，
    # 它的重试策略按来源分派（inject_evidence 自动重放 / dispute 提示用户 /
    # revalidation 整个 job 重跑，见冻结件 `LedgerVersionConflict` 的 docstring）。
    # 这一个说的是「这个 **project 行**被别人改了」，重试就是重读一次再选。
    # 借一个已经有主的码去说另一件事，接的人分不清撞的是哪一条
    # （`DEC-034` / `DEC-038` 反复禁的同一条）。
    "PROJECT_CONFLICT",
    # —— FAV-SNAPSHOT / `DEC-055`：收藏时后端去取证据卡，**没取着**（502）。
    # **NEVER 借 `SERVICE_UNAVAILABLE`**：那一个说的是「这一族没有后端」，
    # 用户该做的是等下一版；这一个说的是「后端在、这一次取不着」，
    # 用户该做的是重试。也 NEVER 与列表屏那句「内容已被清理」共用一句话——
    # 那第三件说的是内容真的没了，重试一万次也回不来（`DEC-055` 边界逐字）。
    "EVIDENCE_FETCH_FAILED",
]

ERROR_CODES: Final[tuple[str, ...]] = get_args(ErrorCode)


class ErrorBody(BaseModel):
    code: ErrorCode
    message: str
    detail: JSON | None = None


class JobView(BaseModel):
    """GET /jobs/{id} 快照（SSE 重连前置读，D8）。"""

    job_id: str
    kind: str
    project_id: str | None
    state: str
    progress: float
    partial_output_ref: str | None
    budget: float
    cost_accum: float
    error: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, job: Job) -> JobView:
        return cls(
            job_id=job.job_id,
            kind=job.kind,
            project_id=job.project_id,
            state=job.state,
            progress=job.progress,
            partial_output_ref=job.partial_output_ref,
            budget=job.budget,
            cost_accum=job.cost_accum,
            error=job.error,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )


class AnalysisSubmitRequest(BaseModel):
    """POST /projects/{id}/analysis 请求体（M2-042 消费）。

    TS-006（owner #5）：加可选 topic_id（向后兼容）。带 topic_id → 由 chosen Topic
    派生 keywords；不带 → 仍走 body.keywords（旧测保持绿）。keywords 默认 []。
    """

    keywords: list[str] = []
    locale: str = "zh-CN"
    budget_cny: float
    topic_id: str | None = None


class DesignSubmitRequest(BaseModel):
    """ENTRY-01：设计生成作业的提交体。

    字段**照消费者真会读的那几个**（`flint/jobs/design_generate.py`）：
    多声明一个没人读的字段，调用方会以为它有用；少声明一个，
    作业会跑起来然后失败，而失败信息里只会说「缺 xxx」——
    没人会想到是入口塞错了。
    """

    model_config = ConfigDict(extra="forbid")

    brief: str
    template_id: str | None = None
    # 与 `AnalysisSubmitRequest.budget_cny` **同名同单位**：两个提交口对同一件事
    # 用两个名字，调用方迟早传错一个。默认 0 = **没声明上限**，
    # 由下游的额度闸决定放不放行——这里 NEVER 替它决定。
    budget_cny: float = 0.0


class AnalysisSubmitResponse(BaseModel):
    job_id: str


class ComboCreateRequest(BaseModel):
    """POST /projects/combo 请求体（TS-010）：选卡（2~5，允许跨簇）+ 一句话关联假设。

    校验/接地口径以后端 create_origin（TS-002）为唯一真相。
    """

    card_ids: list[str]
    hypothesis: str


class ComboCreateResponse(BaseModel):
    project_id: str
    topic_ids: list[str]
    degraded: bool
