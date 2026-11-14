# CLAUDE.md — 燧石 Flint · vibe_pack v2.0（AI 执行包）

> **audience = ai_executor**（PDD v0.3.3）。本包 = 本文件 S1~S9 + `tasks.json`（机器可读任务 DAG）+ `contracts/`（冻结件只读副本）+ `技术方案-v1.1.md`（E1~E12 详版，按 context_refs 章节装载）。
> **规范力标记**：MUST / NEVER 为硬约束；SHOULD 为默认做法，偏离须在 trace 说明；MAY 为可选。标注 `[示例]` 的内容 non-normative，NEVER 当作规范复制进实现。
> 同一信息只在一处定义、他处引用；发现两处矛盾 → 以 contracts/ 与 tasks.json 为准并按 S9 上报，NEVER 自行择一。

---

## S1 Charter

**目标**：V1 商用 MVP——四热点源日更 → 证据卡/工作台/关联假设 → 主题生成 → Gate① 四分类（全引用）→ 深度报告 → 计划书（**受众分叉**：五套人类模板 / vibe_pack AI 执行包）→ 支付（免费额度 + 按次）。

**非目标（V1 边界外，NEVER 实现）**：实时热点；付费数据源（接口留好即可）；英文界面；团队协作空间；B 端 API/白标；四级 VIP 开关（feature flag 先置 false）。

**本包自身范围**：M1 数据与索引层全量 41 任务（S5）；M2~M4/前端为框架，M1 校准后展开。

## S2 Invariants（每 cycle 恒装）

1. `contracts/models.py` 与 `contracts/protocols.py` 是**唯一真相**。NEVER 修改冻结件；类型不够用 → 停止实现，按 S9 写问题单。
2. 三条铁律：结论必有引用；数字必有出处且**三通道互不混用**（Fact / PriceCell / ProfileRef）；产物可复现（唯一例外走 RedactionRecord）。
3. verdict 类 LLM 结构化输出失败 NEVER 猜测——重试 ≤2 后 job failed 并说明。
4. `alignment=="partial"` 的 claim NEVER 提升为 Fact；`status=="disputed"` 的 fact NEVER 被新生成引用。
5. 受保护 block（`locked ∨ author=="user" ∨ user_modified`）NEVER 被 regenerate/shrink/expand 改写。
6. 新增依赖 MUST 先过 RegistryValidator（存在性+最新稳定版），版本 MUST 锁死写入 lock 文件；registry 校验不可用时 NEVER 引入新依赖。
7. CI NEVER 联网；一切外部调用 MUST 走录制回放（M1-008 机制）。
8. **spec/代码注释禁用词**（歧义词，出现即 review_failed）：「适当」「合理」「必要时」「等」「大约」「尽量」「若干」。
9. 每任务 MUST 先把验收写成失败的测试（verify_cmd 所指文件），再实现到通过——顺序不可倒。
10. 不可逆操作（生产部署 / 删数据 / 付费接口开通 / 生产迁移）MUST 人工确认，NEVER 自动执行。

## S3 Contracts

**冻结件**：`contracts/models.py`（全部实体 + 判别联合）、`contracts/protocols.py`（全部接口签名）。实现 MUST 与其类型逐字一致；mypy --strict 是强制执行器。

**技术选型（锁版，全部经 registry 校验 @2026-07-26）**：Python 3.11 / FastAPI 0.140 + uvicorn 0.51 / sse-starlette 3.4.6 / pydantic 2.13（仅边界，域层保持 dataclass）/ SQLAlchemy 2.0.51 + alembic 1.18.5 + asyncpg 0.31 / PostgreSQL 16 + pgvector(1024, HNSW m=16) / Redis 7 + arq 0.28 / httpx 0.28 + selectolax 0.4 + tenacity 9.1 / sentence-transformers 5.6.1（bge-m3）/ scikit-learn 1.9（凝聚聚类）/ anthropic 0.120（LLMProvider 适配器后）/ structlog 26.1 / markdown-it-py 4.2 + weasyprint 69 + python-docx 1.2 / pytest 9.1 + pytest-asyncio + respx / mypy 2.3 strict + ruff 0.16。前端：Next.js 16 + tiptap 3 + zustand 5。逐项理由 → `技术方案-v1.1.md#E1`。

**目录结构**：

```
flint/
  domain/            # 冻结件（只读，S2-1）
  config.py  obs/    # E8 / E7
  sources/           # registry + gtrends/weibo/ghtrend/arxiv（每源一模块）
  norm/  embed.py  cluster/  lineage/  heat.py  signals.py  cards.py
  retrieval/ gate/   # M2
  ledger/  compose/  # M3（compose 含受众分叉：五模板 + vibe_pack 章节族）
  jobs/  api/
tests/  fixtures/  assets/  migrations/  prompts/  docs/  web/
```

## S4 Decision Log + Open Questions

**已决（NEVER 重开讨论；出处即装载地址）**：
- D1~D13 全部（多入口 Origin / Ledger 派生版本 / 两段式对齐 / 干预层四项 / Block 树唯一真相 / Job 状态机 / 多租户 / Revalidator 统一 stale / 判 C 对称 / SSE / 结构化输出降级 / Profile 敏感度 / PriceBook 时效）→ `M0-决策记录.md`
- 判定顺序 A>B>C>D + all_satisfied；strong 竞品 = 任二 signal，unknown 阻断 C → `产品描述文档-v0.3.1.md#2.2`
- Claim/Fact 边界与提升不变量；三出处通道类型化 → `产品描述文档-v0.3.2-终轮补丁.md`
- 受众分叉 / cycle 口径 / review_gate 双 agent 流水线 → `产品描述文档-v0.3.3.md`
- 存储/编排/降级矩阵等工程决策 → `技术方案-v1.1.md` E1~E12

**Open Questions（执行中命中任何一条未决项 → MUST 按 S9 停）**：

| 假设 | 初值 | 状态 |
|---|---|---|
| θ_rel 相关率阈值 | 0.6 | 待金标集调参 |
| 第一段对齐上限 K / 改写轮数 R | 8 / 2 | 待成本实测 |
| cycle 装载上限 | 40k tokens | 待 M1 样板实测标定 |
| estimate_cycles 上限 | 2 | 待样板拆分率 |
| strong=任二 signal | 任二 | 待 20 案例对照 |
| 血缘准确率线 | ≥90%（50 簇） | M1 出口断言 |

## S5 Task DAG

**单位**：cycle := 一次 装载→执行→验证→落盘 闭环。任务 MUST ≤2 cycles（超 → 先拆再动手），目标 1（oneshot）。人日字段为参考值，NEVER 用于排期。

**M1 全量 = `tasks.json`**（唯一机读真相）：41 任务，Σ47 cycles，关键路径 18 cycles，review_gate ×10，verify 覆盖率 100%，DAG 校验 errors=0。每张任务卡含：`inputs`（前置产物溯源）/ `outputs` / `acceptance` / `verify_cmd` / `estimate_cycles` / `oneshot` / `context_refs` / `review_gate`。

**执行规则**：
- 依赖就绪即可领取；无共享文件冲突的就绪任务 MAY 并行（多 agent 各领一个）；
- `review_gate=true` 的任务：verify_cmd 通过后 MUST 经审核 agent 复核（S9 检查单）才解锁下游；
- 估算超限（预估 >2 cycles）= 拆分信号：回 tasks.json 拆分（保持 DAG 校验通过）再动手，拆分记录写 trace。

**M2~M4 / 前端框架（M1 cycle 标定后按同规格展开——展开时 MUST 带 cycles/verify_cmd/context_refs/review_gate）**：

| 批次 | 范围要点 | 规模 | 依赖 |
|---|---|---|---|
| M2 检索与 Gate① | 证据六源 → QueryBuilder（证伪模板）→ RelevanceJudge → 双尺评分 → 两段式对齐 → 竞品强度+Coverage → VerdictResult 引擎 → 金标 20 例 → B7 降级 | 52 | M1-020/033/034 |
| M3 Ledger 与文书 | LedgerStore 乐观锁+diff → ClaimPromoter → ReportComposer（**含受众分叉：五模板 + vibe_pack S1~S9 章节族**）→ Renderer 门禁 → PriceBook/Profile → 干预层 → Revalidator 子批 | 66 | M2 verdict |
| M4 spec 导出 | SpecExporter（ai 路径并入 vibe_pack S5~S7）→ RegistryValidator 实调 → DagValidator（双单位校验）→ 试跑 3 spec | 44 | M3 composer |
| 前端 + F-Editor | 广场/工作台/Gate/报告查看器/**audience 选择器 + vibe_pack 查看器**/SSE 渐进/支付；tiptap↔Block 无损 | 48 | api 就绪 |

## S6 Context Manifest

- **恒装**：S2 + S3 + 当前任务卡（约 6k tokens）；
- **按需**：任务卡 `context_refs`，记法 `文件#锚点`（如 `技术方案-v1.1.md#E4`、`contracts/models.py#Job`、`产品描述文档-v0.2.md#3.2`）——只装列出的章节，NEVER 整本装载 PDD；
- **预算**：单 cycle 装载 MUST ≤40k tokens；超 → 收窄 refs 或拆任务，并在 trace 记录实际装载清单（这就是 M0 trace 的 inputs 来源清单）；
- 前置任务的 outputs 代码 SHOULD 按 `inputs` 字段列出的产物名定位装载，而非全仓浏览。

## S7 Verification Harness

- **约定**：每任务测试文件 `tests/{milestone}/test_{task_id}.py`；`verify_cmd` exit 0 = 机器验收通过。测试 MUST 覆盖 acceptance 的语义（审核 agent 会检查是否空转）；
- **全局门**（M1-007 建立后每次合并强制）：`ruff check . && mypy --strict flint && pytest -q`；
- **流程**：领任务 → 写失败测试 → 实现 → verify_cmd 通过 →（review_gate？→ 审核 agent）→ 写台账（S8）→ 解锁下游；
- **返工环**：verify 或 review 失败 → 按意见修改重跑；**同一原因连续 2 次失败 → MUST 按 S9 升级**，NEVER 第三次盲试；
- fixture 优先：任何外部调用先录制；CI 永不联网（S2-7）。

## S8 Progress Ledger（会话必死前提）

- `docs/progress.jsonl`（append-only，机器可读进度真相）——每行：
  `{"ts","task_id","event":"started|verified|review_passed|review_failed|blocked","cycles_used","note"}`
- `docs/trace/{task_id}.md`：实际装载清单（inputs 来源）+ 断点与决策日志 + 拆分/返工记录——与 M0 推演 trace 同构；
- **新会话启动 MUST**：读 `progress.jsonl` 末 20 行 → 定位在跑/被阻任务 → 读对应 trace → 再动手。NEVER 依赖上一会话的记忆；NEVER 重做 event=verified 之后的任务除非 review_failed。

## S9 Escalation Rules

**停下问 owner（写 `docs/v0.4-问题单.md` 并 blocked）**：
1. 冻结件类型/签名不够用；
2. 命中 S4 未决 Open Question 且无法绕开；
3. 新依赖 registry 校验失败、或只有付费方案；
4. context 预算或 cycle 上限无法通过拆分满足；
5. 同一原因连续 2 次 verify/review 失败；
6. 任何不可逆操作触点（S2-10）。

**审核 agent 检查单（review_gate 任务）**：① 测试真实覆盖 acceptance 语义（非 assert True / 非只测 happy path）；② 无冻结件偏离（类型、签名、判别联合逐字比对）；③ 无 S2-8 禁用词；④ trace 与 progress.jsonl 完整；⑤ 装载未超预算。任一不过 → `review_failed` + 意见写入 trace，任务回 started。

**人审节点（owner 本人）**：里程碑出口报告（M1-041 类）、生产部署、数据删除、付费接口开通。

---

## 附：Human Digest（监工视图 · 1 页 · 不进 AI 上下文）

- **现在在做什么**：M1 数据与索引层，41 个任务，AI 口径总量 47 cycles、关键路径 18 cycles——多 agent 并行时瓶颈是关键路径而非总量。
- **怎么看进度**：`docs/progress.jsonl` 尾部即最新状态；10 个 review_gate 是质量节点，出口在 M1-041。
- **什么时候会被叫**：只有六种情况（S9 清单）+ 三个人审节点；其余时间流水线自转。
- **怎么干预**：改需求走 PDD 修订（owner 变更通道），别直接改 contracts/；对产出不满 → 在对应任务 trace 写意见，标 review_failed。
