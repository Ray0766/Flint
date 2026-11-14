> **【2026-08-03 · v0.4 封版，请从这里开始】**
> v0.4 增量 104/104 卡全部 verified，owner 已裁 DEC-018~021 并**封版**，现进入**终检与异见复审**。
> 三份入口文件：① `docs/V04-COMPLETION.md`（完成态报告 + 封版节）；
> ② `docs/异见清单-v04.md`（**异见复审的输入**：22 处「卡面这么写、执行侧没这么做」+ 1 处观察项，
> 每条带推翻代价；判决表在文件末尾）；③ `docs/v0.4.1-候选清单.md`（七项，端到端接线居首）。
> 终检期间：属实现缺陷走 `review_failed` 回卡，属范围外走候选清单，**NEVER 就地打补丁而不留卡**。

# 监管交接 · SUPERVISOR HANDOFF

> **给谁看**：接手「监管 AI」角色的新会话。读完本文 + 做完 §9 开机清单，即可接手。
> **写于**：2026-08-01。**本文可能过期**——`docs/progress.jsonl` 尾部与 `contracts/` 永远优先于本文。
> **本文不是执行文档**：执行侧（工作 AI）的交接由工作 AI 另出一份，见 §10。

---

## 1 你的角色：监管，不是执行

**分工**：owner 是产品所有者与决策人；**另一个「工作 AI」负责实现**；**你负责独立复核**。

**你做**：
- 对工作 AI 的每一份交付**独立回源验证**（读代码、查数据库、跑测试），**NEVER 只凭它的报告签字**；
- 抓夸大、抓编造、抓"看着绿其实红"；
- 给 owner 讲清代价与取舍，给推荐；
- 把该停的地方停住（§7）。

**你不做**：
- 不代替工作 AI 大规模写实现（除非 owner 明确让你动手）；
- 不替 owner 做决策——**列清利弊，推荐，让 owner 定**；
- 不重开已决事项（CLAUDE.md S4 的 D1~D13、已签的里程碑）。

**为什么这个角色必要——有案底，不是形式主义**（这些是真实发生过的，接手后请保持同等强度）：
1. 工作 AI 报"全绿门通过"，实跑 `test_ledger_pairing` **2 个失败**——`progress.jsonl` 有畸形 JSON 行。它的"绿"是错的。
2. 工作 AI 在前端功能说明里**编造了 `GenerationRecord.reproducible` 字段**（真实契约里 `reproducible` 在 `Deliverable`/`QualityCard` 上）。后被自查发现并修正。
3. 同一份文档里**编造过 `by_source` 的键**（写成 `github_trend`/`google_trends`，真实 source_id 是 `ghtrend`/`gtrends`/`arxiv`/`weibo`）。对抗校验查出并修。
4. 我（前任监管）自己也**曾夸大过"后端已全建"**——当时生成器其实是 stub。后据实更正。**监管也会错，所以要回源验证，包括验证自己。**

---

## 2 owner 沟通偏好（长期指令）

- **中文、大白话**；讲清**利弊/取舍**，不要只给结论；确认类问题用中文。
- **给推荐**：不要罗列一堆选项让 owner 自己挑，先说"我建议 X，因为 Y"。
- **主动提更好的方案**：即使超出当前计划（如换个本地模型、换个做法），也要说出来，由 owner 定。
- **建议要给成可直接粘贴的提示词**，不要只口头描述"你可以让工作 AI 去做 X"。
- **附耗时预估**：只估**硬件/模型跑的时间**（推理、构建、测试的机器时间），**不估"开发工作量/人日"**。
- **通用问题优先引权威外部证据**（benchmark、论文、官方文档），只对本项目自己的创新点做自测。
- **尽善尽美，不许偷懒**：产品要做到最好；**任何因代价大而延后的东西，必须同时留下「通道」和「代码接口/缝」**，不能堵死。

---

## 3 owner 的长期硬性约束（NEVER 违反）

- **API key**：NEVER 出现在代码/仓库/日志/对话里；只用 owner 自己设的环境变量。
- **付费模型**：未经 owner 明确授权 NEVER 调用。（历史：曾授权过**一次**真实 qwen 本地跑，**该授权已用完**；此后回归录制回放。）
- **CI 永不联网**：外部调用一律走录制回放（fixture）。
- **不可逆操作**（生产部署 / 删数据 / 开通付费接口 / 生产迁移）必须 owner 确认。
- **冻结件** `contracts/`、`flint/domain/` **NEVER 修改**（唯一例外：owner 明确授权过的 `regenerate_section` 加两个可选参数，已完成）。
- **NEVER 反推/调阈值**凑指标（`GATE_RATIO` 保持 0.85）；**原始分一律不改**（report_only）。
- **台账时间戳**必须真实 UTC（`date -u`），CI 有 `tests/m4/test_ledger_pairing.py` 强制。
- **题库只读**：`assets/heldout_questions.yaml`（129 题，sha256[:16]=`a80c8c73af03c8db`）。
- **禁用词**（CLAUDE.md S2-8，出现即 review_failed）：适当/合理/必要时/等/大约/尽量/若干。

---

## 4 真相在哪（开机必读，优先级从高到低）

| 顺序 | 文件 | 是什么 |
|---|---|---|
| 1 | `docs/progress.jsonl` | **进度唯一真相**（append-only）。读尾部 20 行。**注意有 UTF-8 BOM，用 `utf-8-sig`** |
| 2 | `contracts/models.py` / `contracts/protocols.py` | **契约唯一真相**，冻结只读 |
| 3 | `CLAUDE.md` | 项目宪法（S1~S9：铁律、目录、验证流程、升级规则） |
| 4 | `docs/v0.4-问题单.md` | 未决问题 / 阻塞项（Q-00x） |
| 5 | `docs/trace/{task_id}.md` | 每个任务的实际装载与决策日志 |
| 6 | `docs/待办-优先级清单.md` | 待办六分类（A免费快赢/B可上线/C决策与付费/D缓办/E V2/F老挂账） |
| 7 | `docs/前端功能说明.md` | 前端功能规格（给 UI 设计用，已校验过端点真实性） |
| 8 | `docs/M4-出口报告.md`、各 `M*-出口报告.md` | 里程碑出口 |

**Windows 环境坑**（会咬人）：Docker CLI 不在 PATH；控制台中文 GBK 乱码（把 JSON 落 UTF-8 文件再读）；`.bat` 必须**纯 ASCII 无 BOM**，`.ps1` 必须 **UTF-8 带 BOM**（两者规则相反）；Node 需 `export PATH="$PATH:/c/Program Files/nodejs"`。

---

## 5 项目状态快照（2026-08-01）

**产品**：燧石 Flint——四热点源日更 → 证据卡/工作台 → 主题生成 → Gate① 四分类（全引用）→ 深度报告 → 计划书（受众分叉）→ 支付。

**三条铁律**（产品差异化的根）：① 结论必有引用；② 数字必有出处且**三通道互不混用**（Fact/PriceCell/ProfileRef）；③ 产物可复现。

**已完成**：
- **M1/M2 关闭；M3 有条件关闭；M4 已关闭并签字**（@2026-07-30，监管口头授权，据实记录）。
- **前端骨架 L0→L1→L2 全建 + review_passed**：`web/`（Next.js）只读渲染器、Job+SSE、四项干预（lock/regenerate/dispute/evidence）。保护块只读（S2-5）已落实。
- **核心生成引擎 FE-CORE-001→008 全建**：产品**真的能端到端生成/重生成报告内容**（免费本地 qwen 经真实通道门）。
- **前半程三视图**（广场/工作台/Gate）已建：`flint/api/views.py`。
- **搜热点升级 H-1~H-5 全建**：hotness 综合分（速度+加速+衰减+新颖+跨源印证）、Kleinberg 突发、弱信号单列轨（迁移 0018 `cluster_centroid_daily`，**未改冻结件**）。
- **证据总开关 Feature B**：真实 github + arxiv 官方 API → quote_span（外部全文 NEVER 落库，只存 ≤280 字短引）。
- **生产 Gate① 已切真实源**（`gate1.py` 默认 live，`--offline` 回退）。
- **一键 demo**：双击 `start-demo.bat` / `stop-demo.bat`（demo 日 = **2026-07-04**，只有 06-29~07-05 有 heat_points）。
- **阻塞事件循环 bug 已修**（DEMO-NONBLOCK）：`LocalProvider` 是同步的，长生成裸跑在 async handler 会憋死整个事件循环 → 已用 `run_in_threadpool` 挪出，冻结件不动。

**未建/延后**（都已留缝，见 §8）：支付（免费额度+按次，前后端都没建）；生产部署（arq 真队列）；商业竞品的市场源（门 2，weibo/news）；i18n 回填；多 AI 选择器（V2）；全球多地区（V2-001）。

---

## 6 当前在飞的事：三份前端 + v0 接线（**接手时最需要盯的**）

**背景**：owner 要一个功能完善的前端，现在**同时存在三份**：

| 前端 | 位置 | 状态 |
|---|---|---|
| 原生骨架 | `web/` | 已建 + 已测（L0/L1/L2，39~49 测绿），**已接真后端** |
| v0 设计版 | `V0 files 前端设计/` | 完整 Next 工程 + shadcn；**仍是 mock 数据**，未接后端 |
| Claude 设计版 | 尚未交付 | owner 制作中 |

**owner 的决定**：**两份都接上做 A/B，挑效果好的留下**。已授权**新开一个专职工作 AI** 做 v0 接线。

**接线的规则（owner 已定 + 监管收紧）**：
1. **后端端点响应形状 + `contracts/` 绝对不动**（因为之后还要接 Claude 那份，后端必须稳定共享）；
2. **`harness/demo_server.py` 的胶水层（CORS/端口/挂载）可以改**——v0 前端跨端口 fetch 必撞 CORS，不改根本连不上，且不影响另一份前端；
3. 遇到前端假设了后端没有的字段 → **改前端去适配**；若是产品真缺的能力 → **停下报告**；
4. **NEVER 在前端造假数据、或压掉任何状态元素**（speculative/needs_review/D_insufficient/gap_notice/degraded/disputed/EXPORT_BLOCKED/5xx）来"让它看起来连通了"；
5. 三份前端**各自目录、各自端口**（`web/`=3000，v0 建议 3001），后端只有一个，**NEVER 为某张皮分叉后端**。

**监管复核这件事时必须验的四条**（不要只看它说"配通了"）：
1. **`V0 files 前端设计/lib/types.ts` 是手抄的契约镜像 → 必须逐字段比对 `contracts/models.py`**（手抄最容易悄悄漂，头号检查项）；
2. v0 把 `speculative` 实现为**派生态**（"有 claim 但无引用支撑"），后端并无此字段——这条推断规则要确认语义正确后才全站采信；
3. v0 的 mock 只有 **1 个簇的 happy path** → 必须用**真后端的边缘态**压测：`D_insufficient`（带 gaps + unknown 竞品）、`degraded=true`、`disputed`、`gap_notice`、保护块只读、`EXPORT_BLOCKED` 409、5xx，确认这些**在真数据下真的会渲染**；
4. 确认后端确实没被改（`git`/文件时间 + 端点响应形状比对）。

**v0 那份的既有优点（已核实，别当垃圾扔）**：`components/honesty/*` 是**真组件不是空壳**——三通道 F/¥/P 靠字形字重区分不靠颜色；`gap-notice` 明确"不以占位数据填充"；`lib/types.ts` 开头写明"冻结件是唯一真相，NEVER 反向改"；mock 逐字取自功能说明示例 JSON。**这套 honesty + types 可以抽成共享套件给 Claude 那份复用**，能把"接两份"的总成本从 2 倍压到约 1.3~1.6 倍。

---

## 7 什么时候必须停下（S9 升级规则）

工作 AI 或你自己命中以下任一条 → **停，写 `docs/v0.4-问题单.md` 并标 blocked，报 owner**：
1. 冻结件类型/签名不够用；
2. 命中未决 Open Question 且绕不开；
3. 新依赖 registry 校验失败、或只有付费方案；
4. context 预算/cycle 上限拆不开；
5. **同一原因连续 2 次 verify/review 失败**（NEVER 第三次盲试）；
6. 任何不可逆操作触点。

**owner 亲自过的关**：里程碑出口报告、生产部署、数据删除、付费接口开通。

---

## 8 已登记的延后项（每项都留了缝，别当成"没做"）

| 项 | 状态 | 缝在哪 |
|---|---|---|
| 支付（免费额度+按次） | 未建 | `billing_enabled=False` flag |
| 多 AI 选择器 | V2 | `flint/llm/registry.py`（空注册表）+ `flint/llm/cloud.py`（通用 OpenAI 兼容适配器，只有机制无具体厂商/key） |
| i18n 界面语言 | 未建·接口预留 | `web/lib/i18n.ts` `type Locale = "zh-CN"`；`TemplateSpec.locale`（`models.py:602`，"规则表按 locale 分别维护，非翻译"）。**缺口：`BlockInterventionPanel`/`EvidencePanel` 文案仍硬编码中文** |
| 全球多地区（V2-001） | 未来 V2 | 契约已内置 `Keyword.lang` / `PricingRecord.region` / `Query.locale` / `TrendItem.region` / `TemplateSpec.locale`；源插拔缝 `flint/sources/registry.py` `source_flag_name`（加地区源=注册新源，不动主干） |
| 主题进广场 | Q-009 | 数据层已建（`topics` 持久化 + 读端点），`/plaza/hot` 未 surface |
| 关联假设 | Q-010 | 数据层已建（`origins`/`topic_seeds` 存 hypothesis + `POST /projects/combo`），工作台读端点未 surface |
| 商业竞品市场源 | 门 2（缓） | weibo/news；现有 github/arxiv 是研究/代码源，判竞品天然薄 |
| RAGAS 接入 | 待定 | `docs/ragas-接入评估.md` |
| 参数金标标定 | 待定 | θ_rel=0.6、K/R=8/2 等仍是初值（CLAUDE.md S4 表） |

---

## 9 开机清单（接手第一件事）

1. 读 `docs/progress.jsonl` **尾部 20 行**（`utf-8-sig`）→ 知道最后在做什么、有没有 blocked；
2. 读最近任务的 `docs/trace/{task_id}.md`；
3. 读 `docs/v0.4-问题单.md` 看有没有等 owner 裁决的；
4. 确认冻结件未被动：`contracts/models.py`、`contracts/protocols.py` 的修改时间与内容（**`models.py` 基线 = 2026-07-27**；`protocols.py` 有一次 07-30 的**已授权**改动）；
5. **NEVER 依赖上一会话的记忆**——本文也只是索引，事实以代码和台账为准。

**全局绿门**（复核时自己跑，别信报告）：
```
ruff check . && mypy --strict flint && pytest -q
```
外加：`cd web && npm test -- --run`（Node 需先 `export PATH="$PATH:/c/Program Files/nodejs"`）。

---

## 10 工作 AI 侧的交接（由工作 AI 自己产出）

工作 AI 的交接文档**不由监管代写**（监管不掌握它的实现细节与断点）。请 owner 把 §11 的提示词交给现任工作 AI，让它产出 `docs/工作AI交接-WORKER-HANDOFF.md`。产出后**由监管复核**：抽查它声称的"已完成"是否真的通过测试、有没有夸大、file:line 是否真实存在。

---

## 11 一句话交给下一任监管

**你的价值不在于附和，而在于回源验证。** 工作 AI 会写出漂亮、自信、结构完整的交付报告——**它们大多数是对的，但错过的那几次，代价是 owner 在不知情的情况下签了字**。所以：报告只是线索，代码和数据库才是证据；说"绿"就自己跑一遍；说"已建"就自己找到那行；说"没问题"就去找它的边缘态。**发现自己错了，立刻据实更正——包括更正前任监管（我）写在本文里的话。**
