# 前端里程碑 · owner 决策备忘（建前端前必拍的四项 + 现在可做的 L0 卡）

> **这份备忘是什么**：M4 已关闭（见 docs/M4-出口报告.md §五）。下一里程碑是前端
> （CLAUDE.md S5：「前端 + F-Editor」批，规模约 48 卡）。CLAUDE.md 规定该批
> **须在架构基线确定后按同规格展开**（展开时每卡带 cycles/verify_cmd/context_refs/
> review_gate）。本备忘 = **展开前的决策闸门**：把「必须你先拍、AI 不能替你定」的
> 四件事摆清（含权衡），并把**唯一不依赖这四件事、现在就能做**的部分（L0 只读
> 渲染器）起草成可执行任务卡。
>
> **纪律边界**：本备忘只规划、不建前端；四项决策 **AI 一律不替 owner 拍**（命中即
> 停、登记待裁，本备忘即登记）。L0 卡草案在 owner 批准前不并入 tasks.json、不动手。

---

## 构建进展（owner Ray @2026-07-30）：Node 解锁 → L0 + L1 已建成、停在 L2

- **Q-005 解除**（owner 选项 1，本机原生 Node v24.18.0/npm 11.16.0）；依赖过 registry
  锁版（S2-6）→ web/package-lock.json（TS pin 5.9.3 兼容）。
- **FE-000 / FE-001（L0）/ FE-002（L1）已建成、review_passed**：web/ Next.js 16.2.12
  只读渲染器（8 类块只读组件 + 分节稳定序 + 保护块只读 S2-5 + chart 零计算 D3，
  NEVER 引 tiptap/zustand）+ Job+SSE 渐进交付（seq 去重 = 断线续订安全 + submit + hook）。
  web 22 测试绿 / tsc 净 / python 全量 1123 绿。
- **4 张前端卡并入 tasks.json**（207 卡，dag_report 重算对账绿，旧版 archive_write
  备份 tasks.json.bak-1，H-3）。
- **停在 L2（FE-003）等 owner**：登记 **Q-006**（V1 首发纳入哪些干预：全干预 vs 薄切片；
  后端 lock/regenerate/disputes/evidence 端点均就绪；受保护 block 只读 S2-5 为硬约束不松动）。
  **NEVER 替 owner 预设宽度。建议先拍 Q-006 解锁 L2。**
- **Q-006 已裁（owner 全干预）→ L2 已建成、review_passed**：据实枚举全干预=4 动作
  （lock/regenerate/dispute/evidence，无 expand/shrink 端点）。FE-003 干预客户端+S2-5 门控 +
  FE-004 UI（保护块前端零改写控件 S2-5 硬断言 / regenerate 复用 L1 Job/SSE / dispute 409
  确认流 / evidence 409 冲突）。web 39 测试绿，L2 卡（FE-003/004）并入 tasks.json（208 卡）。
  **前端主干 L0→L1→L2 全通**。剩 stub：①tiptap vs 块级（FE-EDIT）/③provider-tier 映射
  （FE-SEL）/④i18n（FE-I18N）——待 owner 拍。

## 决策进展（owner Ray @2026-07-30）：批 L0 + 拍 ②

- **L0（FE-001）已批准**：owner「先批 L0（决策无关、现在可做）」。
- **决策②已拍**：owner「拍前端②（解锁 L1/L2）」→ **交付顺序 L0→L1→L2 确认**；
  **L1 与 L2 均纳入 V1 范围（解锁展开）**。L2 干预层的**具体宽度（全干预 vs 薄切片）**
  留到 L2 卡展开时定，本次不预设（AI 不替 owner 拍该子项）。①③④ 仍开。
- **FE-000 已交付（node 无关）**：`GET /deliverables/{id}/blocks` 结构化 Block 树 JSON
  读端点（L0 读契约）test-first 落地并绿——L0 有工具链即可纯前端消费，无需再动后端。
- **环境阻塞 Q-005（已登记）**：本机无 `node`/`npm` → 纯前端（L0 UI 及其后所有前端卡）
  的构建/验收 blocked，**待 owner 择一**（装 Node.js LTS / Node 容器验收 / 暂缓纯前端）。
  详见 docs/v0.4-问题单.md#Q-005。**L0 决策就绪，唯差工具链这一步。**

---

## 一、必拍的四项架构决策（AI 不替你定）

| # | 决策 | 现状（源） | 你要拍的 |
|---|---|---|---|
| ① | tiptap 富文本编辑 vs 块级操作简化 | E10：人类模板路径 = tiptap 3 富文本编辑器；vibe_pack = 只读不进 tiptap | 是否砍掉 tiptap、两条 audience 路径统一为块级操作 |
| ② | 前端交付顺序 L0→L1→L2 | 本备忘提出 | 确认或调整三层顺序与 MVP 范围 |
| ③ | 多 AI 选择器的 provider/tier 映射 + 谁付 key | V2-002（V2 边界）；免费档=本地模型，付费档=Claude | 用户可选哪些档、每档 key 由谁承担 |
| ④ | 前端 i18n 是否预留 locale 缝 | S1 非目标：V1 NEVER 做英文界面；V2-001 呼应 | 现在留 i18n 缝，还是硬编码中文、全部推 V2 |

### 决策① · tiptap 富文本 vs 块级操作简化

- **现状（E10，技术方案-v1.1.md#128-133）**：
  - **人类模板路径 = tiptap 3**：ProseMirror schema 与冻结件 `Block` 判别联合
    一一映射；受保护 block（`locked ∨ author=="user" ∨ user_modified`）编辑器层
    只读；**双向转换无损**是 F-Editor 出口断言（硬指标）。
  - **vibe_pack 路径 = 只读代码风查看器，不进 tiptap**——它的干预是 dispute /
    regenerate 章级操作，NEVER 富文本逐字改（「AI 文档人工逐字改 = 制造漂移」）。
- **要拍的**：保留 tiptap（人类模板可 WYSIWYG 逐字编辑），**还是**把人类模板路径
  也降为「块级操作」（章节级 regenerate / dispute / 就地替换，不做富文本自由编辑），
  两条 audience 路径统一、**删掉 tiptap**？
- **权衡（我不替你拍，只摆事实）**：
  - 保留 tiptap：编辑体验最强（所见即所得）；但 ProseMirror↔Block 无损双向转换
    是**高复杂度硬断言**（F-Editor 出口），维护成本与漂移风险都在这条线上，且引入
    tiptap 3.29 前端依赖。
  - 块级简化：两条路径同构、复杂度骤降、无 tiptap 依赖、与「结构化 block 树为唯一
    真相」的铁律最贴合；代价 = 人类用户失去自由富文本编辑，改为「对某块 dispute /
    regenerate / 锁定」的粗粒度干预。
- **为何 AI 不替你定**：这是**产品形态 + 交付承诺**决策（你对人类用户编辑体验的
  定位），不是工程细节。**命中 → 停、等你拍。**

### 决策② · 前端交付顺序 L0 → L1 → L2

- **三层定义**：
  - **L0 只读渲染器**：把现有 `Block` 树只读渲染成页面（无交互、无 Job、无 SSE）。
    §十/E10 判定「**现在可做**」——它只消费冻结件 `Block` 与既有后端读端点，
    **不依赖①③④任何一项**。
  - **L1 Job + SSE 渐进交付**：创建组稿 Job、EventSource 订阅 `/jobs/{id}/events`、
    按 `PartialBlockEvent` 增量挂载、断线 Last-Event-ID 续（E10 渐进交付 UI）。
  - **L2 干预层**：dispute / regenerate / 锁定 / expand / shrink，受保护 block 前端
    强制只读（呼应 S2-5 与 Block 保护条件）。
- **要拍的**：确认 **L0→L1→L2** 顺序；并明确 **V1 MVP 是否必须含 L2**（还是 L0+L1
  只读+渐进交付即可首发，L2 干预推后）。
- **为何 AI 不替你定**：L1/L2 的范围与优先级是**发布范围**决策（MVP 含不含干预）。
  L0 决策无关、已起草（见 §二）；L1/L2 卡留 stub（见 §三），**待你拍②再展开**。

### 决策③ · 多 AI 选择器 provider/tier 映射 + 谁付 key

- **现状**：免费档 = owner 自托管本地模型（localhost:11434，价目 FREE 实值零）；
  付费档 = Claude（M4 已接通 PaidTierProvider，key 由 owner 在运行环境自配、
  NEVER 入会话/入仓）。V2-002「多提供商选择器」在 V2 边界。
- **要拍的**：用户在前端能选哪些档 / 哪些 provider；每档的 **key 由谁承担**——
  平台统一付、用户自带 key（BYOK）、还是免费档平台付 + 付费档 BYOK？tier→provider
  →计费→key 托管的映射表。
- **为何 AI 不替你定**：这是**商业模型 + 密钥托管（安全面）**决策。**AI NEVER 定 tier
  映射、NEVER 填任何具体 provider key/配置**。Task 4 只做**空注册表骨架 + 通用适配器
  地基**（零 key、零联网、零具体 provider），映射与密钥托管全留给你。

### 决策④ · 前端 i18n 是否预留 locale 缝

- **现状**：S1 非目标明列「英文界面」V1 **NEVER 实现**；V2-001 呼应（未来 i18n）。
- **要拍的**：V1 前端**现在就把文案外置、预留 locale 缝**（为 V2 英文界面留插槽，
  小成本保险），**还是**硬编码中文、把全部 i18n 推到 V2（V1 更简，V2 再回填）？
- **权衡**：预留缝 = 每处文案走一层 i18n key，前期薄成本；后期加语种近零改动。
  硬编码 = V1 最简；V2 回填 i18n 要逐处翻检、成本高。
- **为何 AI 不替你定**：这是**V2 路线权衡**（你对英文/国际化时间表的判断）。

---

## 二、决策无关、现在可做：L0 只读渲染器任务卡（草案，待 owner 批准并入 tasks.json）

> L0 只读渲染既不依赖①（只读，不涉编辑器选型）、也不依赖③④（用中文文案直出、
> 不涉 tier/i18n），且 §十/E10 判定「现在可做」。故**唯一**在四项决策未拍前可起草的
> 前端卡。草案 ID = `FE-001`（最终 ID 由 tasks.json 展开时统一分配）。

```json
{
  "task_id": "FE-001（草案，②已拍解锁；构建待 Q-005 Node.js）",
  "title": "L0 只读渲染器：Block 树 → 只读页面（Next.js）",
  "depends_on": ["FE-000（结构化 blocks 读端点，已交付）"],
  "acceptance": [
    "GET /deliverables/{id}/blocks 返回的结构化 Block 树 JSON 在前端逐块只读渲染：8 类 BlockType（heading/paragraph/table/chart/declaration/quality_card/citation_list/gap_notice）各有对应只读组件，无一类落空",
    "按 Block.order 稳定排序、按 section_id 分节；同一 Block 树重渲染 DOM 结构稳定（快照测试）",
    "受保护 block（locked ∨ author=='user' ∨ user_modified）渲染为只读态、无任何编辑控件（L0 全页只读，此断言防 L2 前回归）",
    "chart 块只按 ChartSpec 的 derived_from 数据渲染，前端零计算（D3 铁律）",
    "citation_list / quality_card / gap_notice 三类系统块结构完整呈现，declaration 块原文呈现不改写"
  ],
  "estimate_days": "参考值，NEVER 用于排期",
  "outputs": ["web/（Next.js 16 App Router 脚手架）", "web/components/blocks/*（8 类只读块组件）", "web/lib/deliverableClient.ts（读端点客户端）"],
  "milestone": "前端",
  "inputs": ["contracts/models.py#Block", "contracts/models.py#BlockContent", "contracts/models.py#ChartSpec", "flint/api/deliverables.py（GET /deliverables/{id}/blocks，FE-000 已交付）"],
  "estimate_cycles": 2,
  "oneshot": false,
  "verify_cmd": "cd web && npm test -- --run（Vitest + @testing-library/react 快照与只读断言）",
  "review_gate": true,
  "context_refs": ["技术方案-v1.1.md#E10", "contracts/models.py#Block", "contracts/models.py#ChartSpec", "flint/api/deliverables.py"]
}
```

- **为何 review_gate=true**：首个前端交付物 + 触及「结构化 block 树唯一真相 / D3 铁律 /
  Block 保护条件」三条不变量的呈现面，须审核 agent 复核（8 类映射无落空、零计算、
  保护块只读）。
- **为何 oneshot=false / estimate_cycles=2**：含 Next.js 脚手架初始化（web/ 尚不存在）
  + 8 类块组件 + 读客户端 + 测试三面，超单 cycle；若展开时预估仍 >2 cycles，回
  tasks.json 拆分（脚手架/组件/测试）再动手。
- **依赖锁版（E10，展开时按 registry 校验 @展开日）**：Next.js 16.2.12；**L0 不需要
  tiptap/zustand**（那是 L2/编辑器的依赖，决策①拍定前 NEVER 引 tiptap）。
- **运行时预测（工作 AI 接手 L0 的耗时估计）**：脚手架 + 8 类只读组件 + 读客户端 +
  快照测试，约 2 个 cycle；工作 AI 墙上时间粗估 **1.5~3 小时**量级（含 npm 装依赖、
  组件逐类实现与快照落定）——瓶颈在 8 类 BlockContent 判别联合逐类映射与 chart 的
  derived_from 反查渲染。**此为参考、非排期承诺。**

### L0 就绪即可交付的工作 AI 提示词（**待 owner 批准建前端后**可直接粘贴）

> 仅在你批准「开始建前端 + FE-001 并入 tasks.json」后交付执行；未批准前不动手。

```
接手 FE-001（L0 只读渲染器）。先读 CLAUDE.md S2/S3 + contracts/models.py#Block/
BlockContent/ChartSpec + flint/api/deliverables.py + 技术方案-v1.1.md#E10。
铁律：结构化 Block 树是唯一真相，前端只读渲染、NEVER 回写、NEVER 计算（chart
只按 ChartSpec.derived_from 数据画）。test-first：先写失败的 Vitest 快照 + 只读断言
（8 类 BlockType 各一、保护块无编辑控件、chart 零计算），再实现到绿。脚手架用锁版
Next.js 16.2.12（L0 NEVER 引 tiptap/zustand）。verify：cd web && npm test -- --run。
过 review_gate。ts 用 date -u，落 docs/progress.jsonl + docs/trace/FE-001.md。
```

---

## 三、卡族（②已拍：L1/L2 已解锁并起草规格；①③④相关仍为 stub）

> L1/L2 因决策②已拍而解锁，下方起草规格草案（构建仍待 Q-005 Node.js 工具链）。
> 编辑器/选择器/i18n 相关卡依赖①③④，保持 stub。所有卡并入 tasks.json + 构建
> 均待 Q-005 解除后按 CLAUDE.md S5「同规格展开」执行。

### 已解锁·起草规格（决策②）

**FE-L1 · Job 创建 + SSE 渐进交付**
- `depends_on`：FE-001（L0 只读组件复用于增量挂载）+ 后端 `/jobs/{id}/events`（M2 已在）。
- `acceptance`：① 前端创建组稿 Job 后订阅 EventSource `/jobs/{id}/events`；② 按
  `PartialBlockEvent` 增量挂载 block（复用 L0 的 8 类只读组件）；③ 断线后以
  `Last-Event-ID` 续订、不重复挂载、不丢事件（模拟断线测试）；④ 终态事件后停止订阅。
- `verify_cmd`：`cd web && npm test -- --run`（EventSource mock + 增量挂载 + 断线续订断言）。
- `context_refs`：技术方案-v1.1.md#E10（渐进交付 UI）、contracts/models.py#PartialBlockEvent、
  contracts/protocols.py#JobEventStream。`review_gate`：true。`estimate_cycles`：2；`oneshot`：false。
- **子决策留白**：若 estimate 超 2 cycles（SSE 客户端 + 增量挂载 + 断线续订三面），
  展开时拆 2 卡（订阅/续订 · 增量挂载）。

**FE-L2 · 干预层**
- `depends_on`：FE-L1（干预经 Job 走）+ 后端 InterventionService（M3 已在）。
- `acceptance`：① dispute/regenerate/锁定/expand/shrink 章级操作经 API 发起；②
  **受保护 block（`locked ∨ author=="user" ∨ user_modified`）前端强制只读、无干预控件**
  （呼应 S2-5 与 Block 保护条件，此为硬断言）；③ 干预结果经 Job+SSE 回流增量更新；
  ④ fact_removed=blocking 的 needs_review 块在导出/分享前强制处理（前端门）。
- `verify_cmd`：`cd web && npm test -- --run`。`context_refs`：contracts/protocols.py#
  InterventionService、contracts/models.py#Block（保护条件）、产品描述文档 干预层四项。
  `review_gate`：true。`estimate_cycles`：2（**L2 宽度全/薄由 owner 在展开时定**）；`oneshot`：false。
- **子决策留白（owner 拍）**：V1 是否要**全部**五种干预（dispute/regenerate/锁定/
  expand/shrink），还是先**薄切片**（如仅 dispute + regenerate）——展开时定，NEVER 预设。

### 四决策定案（owner Ray @2026-07-30）——原 stub 结算

| 决策 | 定案 | 后续 |
|---|---|---|
| ① 编辑器（原 tiptap 富文本） | **指令式重生成（块级）替代**；逐字编辑留 V2（下载 docx 自改）。**tiptap / ProseMirror↔Block 无损双向 NEVER 再做，FE-EDIT tiptap 卡作废** | 指令式重生成的**后端前置未建**（Q-008）+ 粒度块级 vs 章节级待裁（Q-007）→ 裁前不建 |
| ② 交付顺序 | L0→L1→L2 + 全干预（已建成 review_passed） | 完成 |
| ③ 多 AI 选择器 | **推 V2**，V1 只用免费档；FE-SEL 卡整体推 V2 | V1 不建 |
| ④ i18n | **留缝**：最小 i18n 地基随第一个带新串的前端特性落地；旧串回填另起一卡 | 随指令式重生成前端落地（待 Q-007/008） |

> **指令式重生成 STOP（S9）**：查明后端现状——regenerate **执行链未接、无生产组稿 prompt**
> （`_default_generator` 离线确定性；`action=regenerate_section` 无派发消费者；PgRegenerateService
> 仅测试调用）；「穿进组稿 prompt」无 prompt 可穿。冻结 InterventionService.regenerate_section
> 无 guidance 参数。→ **不在假前提上盲建**；后端路径（Q-008）+ 粒度（Q-007）待 owner 裁。
> 铁律好消息：即便接通，用户指令 NEVER 变事实已被通道门结构性保证（draft_section 校验账本外
> 事实即拒稿，无法编造出处）。详见 docs/v0.4-问题单.md#Q-007 / #Q-008。

---

## 四、我的建议路径（供参考，owner 定）

1. **先批 L0（FE-001）**：决策无关、现在可做、给你一个能看见成品的只读渲染面，
   风险最低、最快见效。
2. **同时拍决策②**（交付顺序 + MVP 是否含 L2）：它解锁 L1/L2 的展开。
3. **决策①（tiptap vs 块级）可稍后**：只影响编辑器卡（FE-EDIT-*），不挡 L0/L1。
   我个人观察：块级简化与「Block 树唯一真相 + 防漂移」铁律更一致、复杂度更低——
   **但这是你的产品形态决策，我不替你拍**。
4. **决策③④按 V2 节奏拍**：③在多 AI 选择器真正进 V1 前不阻塞 L0/L1/L2 主体；
   ④若倾向未来做英文，**留缝的边际成本远低于 V2 回填**，但同样由你定。

> 登记：本备忘四项决策同步登记于 docs/v0.4-问题单.md 走向（owner 变更通道）；
> 在 owner 逐项裁决前，前端批 NEVER 展开对应 stub 卡。
