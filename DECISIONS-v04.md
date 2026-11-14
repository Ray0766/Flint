# DECISIONS-v04.md · v0.4 增量的规格外即兴决定

> worker.md §4.3③：影响 ≤3 行的规格外决定记一行（DEC-NNN）后继续；更大的走 blocked 问题单。
> 一行一决定，append-only。

- **DEC-000**（owner 2026-08-02 确认，见 `worker.md` §7）：无人值守连跑授权。事前必审仅四项（生产部署、数据删除、付费接口开通、真实网络或 API key 启用），其余全部转事后补审——里程碑出口 SELFCHECK 写完即进下一阶段、owner_review 卡完成后打标继续、隔离带六卡默认照做。停机条件只有两种：全部卡 verified/skipped_by_owner，或剩余卡全 blocked 且无依赖就绪卡（写 `docs/blocked/SUMMARY.md` 收工）。
- **DEC-001**（PRIN-01）：「工单 §3 正文」的边界定为——从 `## §3 ` 标题行起、到下一个 `## ` 同级标题前止，去掉末尾分隔线 `---` 与首尾空行；`docs/PRINCIPLES-v04.md` 即这一整节（含标题行）。哈希比对前两侧走同一归一（CRLF/CR → LF、去尾部空白），归一后仍是逐字节比对——不归一的话 Windows 编辑器写出的 CRLF 会让两份相同内容假红。
- **DEC-002**（owner 2026-08-02 决定，方案 A）：`worker.md` 移出 `prompts/`，落仓库根 `./worker.md`。原因：`prompts/` 是带 `prompts.lock.json` 的**产品提示词注册表**（既有文件全为 `<名字>@<版本>.md`，由 `flint/llm/prompts.py:58 verify_lock` 守哈希一致），`worker.md` 是 agent 指令文件、不是产品提示词，放进去会让每次改它都要 bump 版本重生成 lock，否则 `test_prompts_lock_clean` 与 `test_repo_lock_is_current` 双红。同步 84 处自引用（tasks-v04.json 2 · WORKORDER-v04.md 2 · worker.md 2 · DECISIONS-v04.md 1 · tasks-m1m4-v04-patch.json 77）。**编号说明**：owner 口述记为 DEC-001，但该号已被 PRIN-01 的 §3 边界决定占用（`docs/trace/PRIN-01.md` 已引用），改号会让既有 trace 指向错误条目，故顺延为 DEC-002。
- **DEC-003**（owner 2026-08-02 定口径）：**v0.4 代码并入 `flint/`，不建 `src/`**。来由：`CLAUDE.md` S3 的目录结构系包模板遗留，与实仓 `flint/` 布局不符；v0.4 以实仓为准，`src/` 口径作废。机械重映射 `src/<x>` → `flint/<x>`：`tasks-v04.json` **48 处**、`WORKORDER-v04.md` **1 行**（§6-H1 的 `grep -R "def .*diff" flint/`）；`worker.md` §5 全局门 `mypy --strict src` → `mypy --strict flint`。**按上下文跳过 153 处前端路径**（`web/src/...` 与 `cd web && npm test -- --run src/...`）——盲替会把 `src/components/native-name`、`src/lib/i18n`、`src/stores/prefs` 这些 web 路径一起改坏。复跑：`validate_dag_v04 --file` acyclic/errors []/coverage 1.0、`ruff --no-cache` 全绿、`pytest -q` 1350 passed。**`flint/` 触碰边界**：以新增子包/新文件为主；既有文件仅允许注册点的只加不删增量（路由注册、JobKind 注册表、E6 降级矩阵、依赖注入装配），每处 trace 留 diff 说明，**NEVER 改既有函数语义**；H 组复用改为包内 import。`CLAUDE.md` 本体零修改，S3 滞后登记见 `docs/blocked/CLAUDE-S3-LAG.md`（非阻塞）。
- **DEC-004**（SCHEMA-00）：`pyproject.toml` 的 ruff per-file-ignores 增 `"contracts_v04/*" = ["I"]`。来由：v04 工作副本**逐字继承**冻结件的 import 排版，给它排序就等于让副本与冻结件产生差异，而「与冻结件逐字对齐」正是 `tools/check_frozen_additive.py` 要守的东西；与既有 `"contracts/*" = ["I"]` 同理同源。
- **DEC-005**（REGION-02）：`flint/grounding.py` **逐字节移动**为 `flint/grounding/__init__.py`，以便新增 `flint/grounding/original_only.py`（REGION-02 的卡上产出路径）。来由：Python 里 `flint/grounding.py` 与 `flint/grounding/` 不能共存——包会盖掉模块，让 11,748 B 的既有代码变成永不执行的死码。移动**内容零改动**（md5 `0f994d146a5a976c47f60d00439390db` 前后一致），`flint.grounding` 这个 import 路径**逐字不变**，6 处既有 import（flint/evidence/enrich.py、tests/m2 ×2、tests/topic ×2、harness/featb_payoff.py）全部照常；全量 `pytest -q` 1472 passed 为证。这不是 DEC-003 意义上的「改既有文件」——函数、签名、语义一个字未动。
- **DEC-006**（owner 2026-08-02 裁决）：**一次性网络授权，仅 `next-intl` 一个包**。安装前过 RegistryValidator（存在性 + latest_stable），版本**钉死**（`web/package.json` 写精确版本、提交 `package-lock.json`），校验记录写 `docs/deps_v04.md`（对应 I18N-01 acceptance）。网络授权**一次性、仅 npm registry**；装完立即回归离线纪律（§4.3⑤ / S2-7 恢复生效）。**除 next-intl 外仍 NEVER 新增依赖**。
- **DEC-007**（owner 2026-08-02 裁决）：**`web/` 是唯一前端工程根**，v0.4 前端代码全部落其中；`前端设计` / `V0 files 前端设计` / `design_handoff` 包只是**参考资产**，NEVER 当工程目录；`_ds` 按 DESIGN-04 挂 `web/public/_ds`。实仓 `web/` 下是 `app/ components/ lib/`（**没有 `src/`**），故照 DEC-003 同款做机械重映射：`web/src/<x>` → `web/<x>`，且 `npm test -- --run src/<x>` → `--run <x>`（vitest 从 `web/` 根跑，路径相对 web 根）。改动：`tasks-v04.json` **126 处**、`WORKORDER-v04.md` 同步、`docs/前端功能说明-v2.md` 同步；残留 `src/` 扫描为空。复跑 `validate_dag_v04 --file` → acyclic / errors [] / coverage 1.0。
- **DEC-008**（I18N-02）：i18n 扫描面**排除测试文件**（`*.test.*` / `*.spec.*` / `__tests__/`）。来由：测试里的中文是**断言数据**，不是发给用户的界面文案；把它们也 key 化，测试就变成「断言 `t('some.key')` 等于 `t('some.key')`」——不再验证用户看到什么，反而把测试削弱成同义反复。扫描面因此是**要发出去的源文件**。注释行同样不计（注释不发给用户）。
- **DEC-009**（I18N-02）：组件取文案走 `web/lib/i18n/t.ts` 薄封装，而非直接在组件里用 `useTranslations`。来由：既有 11 个组件测试是**直接渲染组件**的（无 Provider），若组件强依赖 Provider，每个测试都要包一层，而那层包装除了「让测试跑起来」之外不验证任何东西。薄封装的两条路径（有 Provider 用 Provider、无则回落 zh 词条）取的是**同一份 messages**，故测试断言到的文案与用户看到的逐字相同——NEVER 出现「测试断言 key、用户看到文案」。key 缺失时返回 key 本身并告警，NEVER 返回空串（空串会让界面出现一块无声的空白，比显示 key 更难被发现）。
- **DEC-010**（HOTSPOT-03）：分析界面的 **cluster→Gate① 判定** 对应关系由**调用方给出**（`AnalysisView` 的 `verdictJobId` 入参），视图与端点 NEVER 自行推断。来由：卡片 inputs 写的 `GET /clusters/{id}/verdict(既有)` 在真件里不存在，判定按 job 键落在 `snapshots['snap-{job}-verdict']`；而 `contracts/models.py#Job` 无 cluster 字段、`VerdictResult` 无 cluster_id、`jobs` 表也无 cluster_id ——这条对应关系当前**没有持久化真相**，补它就是编造溯源链，猜错时用户会看到**另一个热点的判定**并把它引进计划书。缺省 `verdictJobId` 时渲染「未判定」态且**不发 verdict 请求**。矛盾已按 §1.4 上报：`docs/blocked/HOTSPOT-03.md`（非阻塞，待 owner 在甲/乙两案里点一个）。
- **DEC-011**（HOTSPOT-05）：分析结果缓存的**键**保持卡上 acceptance 逐字口径（cluster + lang + 档位 + 账本版本），**查表另在 owner 命名空间内进行**（`store.get(owner_id, fingerprint)`）。来由：缓存回的是**别人那次运行的 job_id**，同一把键跨租户命中等于把另一个账号的作业交出去（D7 多租户）；把 owner 塞进键会偏离 acceptance 写死的四要素，故改为命名空间隔离——四要素一字未动。附带两条同源判断：`ledger_version is None` 时整条缓存路径跳过（不查不写，宁可多跑一次也 NEVER 回一份无法证明时效的结果）；指纹拼接对分隔符 `|` 转义（否则 `("c-1|zh","")` 会与 `("c-1","zh")` 撞同一个键）。
- **DEC-012**（owner 2026-08-03 裁决 · HOTSPOT-03 问题单）：**选甲——cluster→Gate① 判定的对应关系由调用方（路由层/上层页面）持有**，`AnalysisView` 的 `verdictJobId` 入参形态维持不变（DEC-010 继续有效），`docs/blocked/HOTSPOT-03.md` 关闭。**乙案**（真建 `GET /clusters/{id}/verdict` + 对应关系持久化）登记为 **v0.4.1 候选**，与 §9-P1（收藏快照 pin）、§9-P3（design_delta 与 SSE replay 语义）同批再议；在那之前 NEVER 自行开工，也 NEVER 在任何卡里假定该端点存在。
- **DEC-013**（owner 2026-08-03 裁决 · i18n 补记）：认可 `docs/trace/SELFCHECK-V2.md` 追记的结论——「整棵 `web/` 树 i18n_scan exit 0」当时并不成立。三项收尾（① 扫描器 `cjkLines()` 剥掉跨行块注释，消除 JSDoc 假阳性；② `app/deliverables/[id]/page.tsx`、`app/jobs/[id]/page.tsx`、`app/layout.tsx` 三处真实文案 key 化；③ 清掉 `web/lib/i18n.ts` 这份与 `messages/` 重复的 v0.3 遗留词条表）MUST 在 **V5 出口前**完成；届时 `node tools/i18n_scan.mjs web --fail-on-cjk` exit 0 **升格为 V5 出口判据**。为免只留在决定记录里被漏掉，本条同时落成机读卡 `I18N-09`（tasks-v04.json，V5，verify_cmd 即该命令）。
- **DEC-014**（GRAPH-06）：新增 `flint/graph/roles.py` 作为「图内主唯一」的**运行时落点**（卡片 outputs 未列，acceptance② 要求）。来由：契约 `set_primary` 是作用在列表上的**纯规则函数**，没有运行时落点可供并发测试打；只用它写测试，测到的是「规则在单线程下成立」，而那是 SCHEMA-12 已验过的东西。新文件而非改既有文件，符合 DEC-003 的触碰边界。写入在一个临界区内完成「清旧主 → 立新主」：内存实现用锁，SQL 实现的等价物是同一事务 + `UNIQUE (graph_id) WHERE primary` 部分唯一索引（语义相同，已写进模块 docstring 免得接 SQL 时有人以为锁是内存实现的特产）。同文件另带反例探针 `naive_set_primary_unsafe`，docstring 写死 NEVER 用于生产路径——它存在的唯一理由是让并发断言证明自己认得出违规。
- **DEC-015**（GRAPH-07）：`flint/api/schemas.py#ErrorCode` 增一个成员 `EMPTY_HYPOTHESIS`（既有文件的**注册点只加不删**增量，DEC-003 允许的形态），并新增 `flint/api/graph_edges.py` 承载 `POST /workbenches/{id}/edges`。来由：acceptance 要的是「绕过前端直发 → **422 EMPTY_HYPOTHESIS**」，那是一次真实 HTTP 往返，函数级测试出不了状态码；而单列一码而不是并进 `VALIDATION_FAILED`，是因为「边上没写假设」与「请求体格式不对」的修法完全不同——前端要据此把光标送回假设输入框，而不是弹一句通用报错。既有断言 `tests/m2/test_m2_041.py`（错误码 UPPER_SNAKE + 必含四码）复跑通过。
- **DEC-016**（DESIGN-17）：把 DEC-007 机械重映射漏掉的**两处光秃秃的 `web/src`** 补齐为 `web`——`tasks-v04.json` 的 `DESIGN-17` 与 `DESIGN-23` 两条 verify_cmd（扫描器实参），以及 `WORKORDER-v04.md#5-G` 对应的两行。来由：DEC-007 的模式是 `web/src/<x>` → `web/<x>`，末尾不带路径段的裸 `web/src` 没被命中；而 `web/src` 目录并不存在，照原样跑扫描器会因为目录不存在而失败——那种红查起来像工具坏了，实际是路径写错了。复跑 `validate_dag_v04 --file` → acyclic / nodes 104 / errors []。
- **DEC-017**（DESIGN-21）：`_ds` 副本的 `fonts/fonts.css` **移除两条外部 `@import`**（cn-fontsource 得意黑 + Google Fonts 三款），改为走 `tokens/typography.css` 已声明的回落栈（Inter → Noto Sans SC → PingFang SC → system-ui）。来由：交付出去的文件带着外部字体引用，会在**客户机器上**向第三方要东西——内网/离线打不开、对方能看见谁在什么时候读了这份文件、CDN 改版时早已交付的文件会自己变样（与 DESIGN-20 依赖白名单同一条纪律）。自托管需要 woff2 **二进制**，而取得它们要联网下载 = §7 事前必审项，NEVER 自行触发；`_ds` 自己的 readme 也写着「if the user provides binaries」。**后果登记**：得意黑与 IBM Plex Mono 退成系统字体（只影响视觉观感，不影响数据/判定/导出正确性），待 owner 提供二进制或明确接受回落——`docs/blocked/DESIGN-21-FONTS.md`（非阻塞）。
- **DEC-018**（owner 2026-08-03 裁决 · DESIGN-21 字体）：**接受系统回落字体**，`docs/blocked/DESIGN-21-FONTS.md` 关闭。品牌字形（得意黑首屏大字与页面级标题、IBM Plex Mono 数值）在 v0.4 交付形态里退成回落栈（Inter → Noto Sans SC → PingFang SC → system-ui），**只影响视觉观感，不影响数据、判定与导出正确性**；DEC-017 的「产物 NEVER 向外部要字体」继续有效，`tools/no_external_fonts.mjs` 保持出口门。woff2 自托管移入 v0.4.1，与端到端联调同批处理。**留下的接口**：`web/public/_ds/…/fonts/fonts.css` 里已写死自托管的 `@font-face` 接法与放置目录——补二进制时只加文件、不改结构。
- **DEC-019**（owner 2026-08-03 裁决 · 三份措辞/滞后登记单）：**均认可登记结论，照登记关闭**。其中两单的登记结论各带一处措辞对齐，已执行——① `SCHEMA-05` acceptance ①「frozen 拒二次赋值」→「**写路径**拒二次赋值」（对齐真件：`Cluster` 是非 frozen dataclass，写一次由 `__setattr__` 守）；② `REGION-06` 卡名与 acceptance ①「authority 轴接 `EvidenceScore.axis`」→「接入 axis 体系、**记于 `EvidenceScore.components`**」（对齐冻结件：`EvidenceOrigin` 只有 retrieved / user_provided 两值），`WORKORDER-v04.md` 同口径两行（L39、L390）同步。**为什么要真去改这两处字**：矛盾留在机读真相里，下一个读 `tasks-v04.json` 的人会照字面把 `Cluster` 改 frozen、把第三值塞进 `EvidenceOrigin`——问题单关掉了，坑还在原地。③ `CLAUDE-S3-LAG` 照登记的第一选项**保持现状**：S3 目录结构作为概念分层示意永久留档，落点真相以 `tasks-v04.json` 为准，`CLAUDE.md` 本体**零修改**（owner 变更通道，NEVER 由执行侧改）。改后复跑：`validate_dag_v04 --file` acyclic / nodes 104 / errors [] / coverage 1.0；`test_i4_names.py` + `test_scorer_axis.py` 17 passed；`tests/v04/principles` 5 passed（改的两行在 §3 正文 112~166 之外，PRIN-01 哈希不受影响，测试为证）。
- **DEC-020**（owner 2026-08-03 裁决 · v0.4.1 候选清单确认）：清单与**次序**确认，落 `docs/v0.4.1-候选清单.md`——**① 端到端接线 + 真实 demo 跑通（首位）**，其后 ② 乙案 cluster→判定持久化（DEC-012）、③ §9-P1 收藏快照 pin、④ §9-P2 判据注册表、⑤ §9-P3 design_delta ephemeral、⑥ undo 链三处接线（GRAPH-04/07/09）、⑦ 字体 woff2 自托管（DEC-018）。**P2 的「采纳窗口已随基线实现关闭」**：判据注册表若要当作统一抽象，须在两道闸门（DESIGN-16/32）落地**之前**引入；基线已按两条判据实现并 verified，此刻再改就是重构而非采纳，故 P2 **并入本批**按重构评估，NEVER 追溯改 v0.4 已 verified 的闸门实现。
- **DEC-021**（owner 2026-08-03 裁决 · 封版）：**v0.4 增量封版**，进入 supervisor **终检与异见复审**。封版后执行侧对 v0.4 范围内的实现与判据 **NEVER 再改**；终检期间发现的问题两条出路——属实现缺陷走既有 `review_failed` 通道（回对应卡 + trace 写意见），属范围外走 v0.4.1 候选清单，**NEVER 就地打补丁而不留卡**。异见复审的输入是 `docs/异见清单-v04.md`（执行期 **22 处**「以真件/纪律压过卡面字」的判断 + 1 处终检观察项逐条列出，每条带卡上原话、我做了什么、为什么、**推翻它要连带改多少已 verified 的卡**；判维持的条目此后不再重开）。
- **DEC-022**（owner 2026-08-04 裁决 · 网络授权）：**三档授权，纪律随行**。① **档 A 只读调研**——WebSearch / WebFetch 查权威资料（源站清单、权重方法论、支付接入、交互设计），只读、不登录、不提交表单；② **档 B 真实源抓取**——真跑源站取数据，**抓完 MUST 录进 `fixtures/`**；③ **档 C 付费 API**——见 DEC-023。**S2-7「CI 永不联网」不作废、而是精确化为「采集阶段可联网、验证阶段恒回放」**：`NET-01` 把这条做成扫描器（采集脚本白名单豁免并逐条列名，验证面出现裸网络调用即红），`NET-02` 要求抓来的每条数据带 **URL + 真实 UTC 时间戳 + 内容 sha256** 三件套，缺一即拒绝入库。来由：owner 需要真实数据看效果，而 `S2-7` 的目的是**产物可复现**，不是禁止联网——分档之后两者同时成立。**仍属事前必审、NEVER 自行触碰**：生产部署 / 数据删除 / **付费网关开通与真实商户密钥** / **`NET-03` 真实源冒烟的首次执行**（留卡，需 owner 在场）。

- **DEC-023**（owner 2026-08-04 裁决 · 付费模型授权）：**授权三家，分工不同，不设单次额度上限**。① **DeepSeek V4 Flash = 产能**（$0.14/$0.28 每百万 token，标定一轮约 0.85 元），承担标注、重判、机审的全部跑量；② **Claude = 第一校准点**（余额 $10，单次校准 ≤$1）；③ **GPT-5.6 = 第二校准点与仲裁票**（余额 $20），**三档按用途分工**：**Luna** $0.20/$1.20 → 大批量低难度分类（K5 英文文案初筛）与 DeepSeek 的产能备胎；**Terra** $2/$12 → **校准票**（默认）；**Sol** $5/$30 → **仲裁票**，三家分歧时才动。**校准票 NEVER 用 Luna**：校准票是「当裁判的裁判」，必须至少与被校准者同级或更强，而 Luna 与 DeepSeek V4 Flash 同级——拿它校准则一致也不代表对、不一致也无法归因；整批只需 1~3 次校准，Luna 相对 Terra 只省不到 3 美元，换不来这个代价。**不设额度上限的依据**：三家均已关闭自动充值，**余额本身就是硬上限**；正常一轮标定 0.85 元，余额 100 元可跑约 100 轮。**稀缺额度买信息不买产能**：Claude 与 GPT 的余额只用于判官对齐检验（`JUDGE-02`），NEVER 用来跑量。**API key 只从环境变量读**，永不进代码、仓库、日志、trace、对话。每次调用记账（token 数 / 金额 / 用途），账本 append-only 可对账。

- **DEC-024**（owner 2026-08-04 裁决 · 支付进 V1）：**用别人的托管收银台，NEVER 自建支付系统**——微信支付 / 支付宝 / Apple Pay / PayPal，用户在**对方页面**付款，我们只收结果回调。**NEVER 存储卡号**（不碰卡号 = 不进 PCI 合规面）。**计费基准 = 每次对话实际消耗的 API 用量**：从既有 LLM 记账取真实 token 数，乘配置里的单价。**四条安全边界做成机器可验**（`PAY-03`，每条配阴性对照并接进全局门）：① 仓库/日志/trace 里零支付密钥；② 回调 MUST 验签；③ 扣费 MUST 带幂等键，同一笔重放只扣一次；④ 代码里零卡号字段。**金额恒服务端计算，NEVER 信前端传来的价格**。**多币种**：显示价与结算价分离，汇率取值**带出处与时间戳**。**价格数值（K7 免费额度与按次单价、K8 币种与汇率分档）仍未定** → 全部从配置读，**配置留空 = 整条计费路径关闭**，行为与今天逐字相同（阴性对照证明）。**真实商户密钥启用属 §7 事前必审**，本批留卡不执行。

- **DEC-025**（owner 2026-08-04 裁决 · 冻结件修订 · 方案 A）：`Doc` 增三个字段——**`content: str | None`**（正文**进库**）、**`content_sha256: str | None`**（原文哈希）、**`content_truncated: bool`**（截断标记）。走 **additive 通道**（`contracts_v04` 工作副本 + `check_frozen_additive.py` 双通过），`contracts/` 本体在 `DOC-01` 卡内**一字不动**。**为什么选正文进库而不是引用外部存储**：外部存储会产生「库里有指针、文件没了」的**孤儿**——两个存储就是两个真相，与「产物可复现」「结论必有引用」两条铁律正面冲突，而本项目已经在孤儿上栽过一次（`test_m4_023` 的 orphans 缺陷藏了 28 小时）；体量上一年 0.4~3.6 GB 对 PostgreSQL 很小，且 PG 的 **TOAST** 机制已自动把大字段压缩并存到行外，「正文拖慢库」这个担心在 PG 上不成立。**截断上限 2 MB**（owner 2026-08-04 由 steward 初拟的 256 KB 加码至 2 MB）：约 70 万汉字、≈ 一部《红楼梦》，任何单篇论文/深度报道/白皮书都装得下且余量巨大。超限截断并置 `content_truncated=True`，**NEVER 让下游以为拿到的是全文**；超限原件走已留好的 `source_file_ref` 缝进文件系统，**不丢数据、只换存放位置**。**为什么不设成几个 GB**：① PostgreSQL 单字段物理上限就是 1 GB（varlena 硬限制），写不进去；② 上限的作用不是省空间而是**挡异常**（无限滚动页、被注入垃圾、解析器把导航当正文、抓到 dump 文件）——设成 GB 级等于没有上限，一次异常抓取就能让单条记录吃满内存、把备份从几分钟拖成几小时，而且是**静默发生**的。**PDF 原件例外**：原件走文件系统，`Doc` 只留可选 `source_file_ref`——**正文进库、原件进文件**。

- **DEC-026**（owner 2026-08-04 裁决 · 前端唯一一套）：**`web/` 是唯一前端工程根**（`DEC-007` 维持不变）。`Claude design Flint 前端设计/` 与 `V0 files 前端设计/` 是**视觉与交互蓝本**，NEVER 当工程目录。**风格照蓝本、内容照后端**：后端有的才显示，没有的**如实标「接口未提供」**，NEVER 照搬蓝本里后端做不到的部分。拿不准的交互形态先搜权威产品怎么做，**参考出处写进 trace**。`V0 files 前端设计/node_modules`（2.99 GB）owner 2026-08-04 决定**不删、保持现状**。

- **DEC-027**（owner 2026-08-04 裁决 · K 组解锁 + Z 线）：K 组从「等外部输入」改为「自己去查，查完直接做」。① **K1 源站清单**——搜权威来源产出清单，**每条附出处链接与调研日期**，按 `REGION-01` 准入标准打分后接进 `SourceRegistry`；查不到就写「未找到公开端点」，**NEVER 凭印象列站名**。② **K2 抓取合规**——现阶段**非商业用途，能获取的直接获取**；但状态要**照实记录**（能访问就记实测值），并留 `docs/blocked/K2-COMPLIANCE-BEFORE-LAUNCH.md` 登记「上线前须补手续」；既有 `fetch_gate` 的阻断能力保留不删，只是配置为不阻断。③ **K3 authority 权重**——搜方法论定值，替掉 1.0 中性占位，`revisit(K3)` 标记随之移除；**改权重必须真的改排序**（构造数据证明）。④ **K4 翻译**——本地模型优先，太贵则接谷歌免费档；产物标记翻译来源。⑤ **K5 英文文案**——DeepSeek 机审，但**审过 ≠ 定稿**，仍带 `needs_review` 直到人工确认。⑥ **K6 多工作台交互**——照 Claude design 风格实现。⑦ **Z 线初值**——参考权威标准 + 本项目实际运行数据给出初值并**从 report_only 升为可判定**；owner 明确：**NEVER 因为本地条件通不过就把线一直悬着**——线先画上，达不到是另一件事。

- **DEC-028**（owner 2026-08-04 裁决 · 三项维持不做）：① **RAGAS 接入**——维持既有结论，依赖闭包翻倍且空卡上跑价值低，**等 `DOC-03` 把证据卡做厚之后再议**；② **生产部署**——主链刚接通、界面刚重做，部署一个还没成形的产品得到的是「能访问的半成品」，代价是从此要维护它；**等本批做完、界面能看再议**；③ **逐张回源终检（20~30 小时）**——两段式终检已挖出 8 条真缺陷，边际收益递减，改由 `GAUGE-02` 的「acceptance ↔ 尺子」专项清点覆盖全部 104 张卡（成本低一个数量级，且正中病根：8 条缺陷里 4 条是「压根没有那把尺子」）。

- **DEC-029**（owner 2026-08-04 裁决 · 第 2 批一次性连跑）：v0.4.1 第 2 批 **86 卡 / Σ116 cycles / 关键路径 7**（`docs/steward/tasks-v041-b2.json`，DAG 校验 errors []）**一次性跑完，不拆批**。高风险的 7 张（`DOC-01/02/03` 冻结件与证据补厚、`PAY-01/02/03` 支付、`NET-03` 真实源冒烟）以 `depends_on` **钉在末尾**——**这只是排序，不是停机点**：`DOC-01` 依赖 `GAUGE-01/02`，即「先把尺子修好、清点完，再动被尺子守着的东西」（终检刚证明尺子会骗人，F-11 两把尺子一红一绿）。**停机条件仍只有两种**（全部 verified/skipped，或剩余全 blocked），**NEVER 中途停下等 owner**。**判官对齐不达标时 NEVER 停机**：走三判官降级链——拉 GPT 作第三票 → 两家一致的采纳 → 三家都不一致的条目标 `needs_owner_review` 单独列进分歧清单**并继续跑**；三家全不可用时降级为「只用 DeepSeek + 标注未校准」，**照实标注、继续跑**，NEVER 假装校准过。

- **DEC-030**（worker 2026-08-04 · GAUGE-04 执行中 · ≤3 行影响，按 worker.md §4.3③ 记一行继续）：`WORKORDER-v04.md:527/528` 两条里程碑门命令里的 **5 个 `src/` 过滤器**按 DEC-007 补完重映射（`src/views`→`views`、`src/components/graph-edge`→`components/graph-edge`、`src/lib/undo`→`lib/undo`、`src/lib/graph-layout`→`lib/graph-layout`）。**这是终检 F-08 逐字给出的修法**，且卡面 outputs 只列了新增的两个文件，故在此登记：改的是**两行文本、5 个 token**，无语义改动。依据：`web/src/` 在 DEC-007 之后不存在，vitest 对匹配不到的过滤器**静默丢弃且仍 exit 0**——本机实测 V4 门按修前写法只跑 1 文件 / 6 tests（本该 16 文件 / 128 tests，**4.7%**）并报绿；V3 门 21 文件 / 143 tests（本该 31 / 225）。修后两条门的过滤器全命中，实跑数与本意一致。影响面已核：`check_principles_doc.py` 只哈希工单 **§3**（527/528 在 §8，区外），`check_techplan_delta.py` 只从工单收 CamelCase 类型名（本次未动类型名）——两把尺子改后仍绿（`pytest tests/v041/test_doc_gates.py tests/v04/principles -q` → 14 passed）。治本件同卡交付：`tools/check_vitest_filters.mjs` + `tests/v041/test_vitest_filters.py`，**已接进 `pytest -q`**，此后任何人往门里写一个匹配零文件的过滤器都会当场红。
- **DEC-031**（owner 2026-08-05 裁决 · v0.4.1 第 3 批首卡 = API 装配）：**第 3 批以「API 装配」为首卡**。`flint/api/app.py` 至今只挂 `/categories`，**62 条路由中 51 条够不到**（`AUDIT-01` 实测，steward 复核源文件属实）。装配卡的验收 **MUST 包含逐条探活断言**——**「挂上了」NEVER 等同于「能通」**；**仅断言 `include_router` 存在判为空转**。`tools/check_fe_be_parity.py` 的 **`backend_not_assembled` 计数归零是出口判据**。**编号说明**：owner 口述记为 DEC-030，但该号已被 GAUGE-04 的规格外登记占用（`docs/trace/GAUGE-04.md` 已引用三处，改号会让既有 trace 指向错误条目），故按 `DEC-002` 的先例顺延为 DEC-031；本条与其后两条的口述号统一 +1。**落地时发现并修好的一处**：该出口判据在原实现下**永远不可能达成**——`mounted_paths()` 按源码字面量扫 AST，而装配的惯用写法 `app.include_router(x.router)` 这一行里没有任何路径字面量，实测量到 0 条挂载；装配卡做对了，计数仍停在 51，且红着的样子与「真没装配」逐字相同。已改成**问建起来的应用要它的路由表**（递归展开 FastAPI 0.140 的 `_IncludedRouter` 惰性节点 + `include_context.prefix`），并 NEVER 走 `app.openapi()`（那份 schema 漏掉 `include_in_schema=False` 的路由，一条隐藏路由就能把出口判据永远卡住）。建不起来时**报一条 `app_unbuildable`、零条 `backend_not_assembled`**，不拿空集合印出一份与「62 条全没挂」逐字相同的报告。变异考 6 条全咬住 + 假变异对照绿。
- **DEC-032**（owner 2026-08-05 裁决 · 未装配期间的界面口径 · 一次裁完 UI-01~11 的共同问题）：**未装配期间前端一律显示「接口未提供」，NEVER 显示空态／未启用／隐藏入口**。理由：**没查过 ≠ 空的／坏的**，空态会让用户以为已查证。两处随之定死：① **`UI-11` 照真件**（`BE-01` 已建 `GET /projects/{id}`），**NEVER 照蓝本 P14 那句已失效的「无专属端点：topics + jobs + deliverables 组合」**；② **`UI-09` 陈旧横幅在未查证时 NEVER 挂出**。**本条随装配落地自动失效**——组件里两条路保留，切换成本一行。落地实况：这正是 worker 在 UI-01~11 十一张卡上已经采取的做法（`NotProvided` 与空态各带自己的 `data-*-state`），故本条**确认既有实现，无代码改动**；十一张卡的 `owner_review` 共同问题就此结案。
- **DEC-033**（owner 2026-08-05 裁决 · `NET-03` 拆两半结案）：① **「跑一次真实 github/arxiv 检索」已由 owner 2026-07-31 payoff 执行并录制**（`docs/生产Gate1-真实源切换-payoff.md` + `fixtures/gate1_live/`）→ **`NET-03` 标 `skipped_by_owner`，理由逐字记入台账，NEVER 按「已登记未执行」写判据**（那句话今天是假的，钉成回归比不写更坏）；② **「经作业队列（`jobs` 表 → `worker_main` 消费）跑通 gate1」缺的是 `gate1_deps` 注入而非网络授权** → **单开普通卡，走 respx 回放验证，NEVER 继续挂红线**。**若该链路在回放下暴露出真实网络请求，立即回退为红线卡并停下上报。**对应 `docs/blocked/NET-03-CARD-PREMISE-STALE.md` 提出的三选一：owner 取的是**「甲 + 乙 各一半」**——甲（卡面过期）适用于①，乙（队列链路且允许回放）适用于②。该问题单就此关闭；②的新卡登记在 `docs/积压总账-v041.md`，由 steward 编进第 3 批。

- **DEC-034**（worker 2026-08-07 · DS-02 执行中 · ≤3 行影响，按 worker.md §4.3③ 记一行继续 · **请 owner 事后裁**）：**Gate 四分类 NEVER 一一映射到 `_ds` 的内容状态八态**。素材 `CardStack.dc.html` 的卡面右上角在五张示例卡上是五个不同的记号，本想让 `A_infeasible`/`B_red_ocean`/`C_opportunity`/`D_insufficient` 一一对上；核过之后不能那么做——**`_ds` 八态在本仓每一个都已经有主**：`disputed` 是 fact 的 `status=="disputed"`（S2-4：NEVER 被新生成引用）、`sealed` 是被锁的 block（S2-5）、`degraded` 是 B7/E6 的降级生成、`speculative` 是还没提升的 claim、`blocking` 是阻塞/409/503。把 `B_red_ocean` 涂成 `disputed`，屏上「这条结论有争议」与「这个赛道是红海」就共用一个记号，而前者是铁律级的事实状态——**借一个已经有主的记号去说另一件事，比不给记号更坏**。落地取零冲突的那一档（`web/components/hotspot-card/verdictStatus.ts`，2 行）：`D_insufficient` → `void`（证据不足 = 有形空缺，语义逐字相同），其余三类 → `verified`（共同点：判定已出且全引用，Gate① 铁律），**分类本身由标签文字承载**（人类标签在 `DS-03`）。**代价说清楚**：A/B/C 三类在记号上看起来一样，比素材少一层可扫性。**若 owner 要四档各有各的记号，那是给 `_ds` 加记号，不是借现成的**——那属于设计决定 + 动供应商资产（终检 C6），NEVER 由一张卡面卡自决。

- **DEC-035**（owner 2026-08-08 裁决 · 地区面走迁移，不绕）：`PLAZA-02` **停得对，本批重做**。规格 `docs/前端功能说明-v2.md#2.14` 白纸黑字写着「`GET /plaza/hot?region=`【已建，增 query】」，而 `flint/api/views.py:66` 的签名只有 `day`——**FastAPI 对未声明的 query 静默忽略**，实测带 `region=CN` 照样回全量 154 条。**一个静静地什么都不筛的筛选器比没有筛选器更坏**：用户会把「全国的热点」读成「这个区的热点」，并据此做判断。**代价已核清**：`clusters` 表列是 `cluster_id · canonical_name · category_id · centroid · status · first_seen · last_active · parent_cluster_ids · merged_into · aliases`——**没有 region**；`heat_points` 也没有；`region` 今天只活在 `trend_items_raw`（0004 迁移）与 `flint/region/bucketing.py` 的 `RegionCluster`（模块内 dataclass，**从没落过库**）。**所以要迁移**：`clusters` 加 region 列 + 回填 + 日更作业写入，落在 `REGION-08/09/10` 三张卡上（迁移号 0021）。**回填有一条硬规矩**：`region` **随成员走、NEVER 靠簇去推断**（`bucketing.py` 自己的原话）——回填时撞见成员跨区的簇 → **停下上报，NEVER 取众数**，那说明数据面已经破了 `PRINCIPLES#B5`。影响面：`migrations/versions/0021_*.py` · `flint/api/views.py` · `flint/jobs/ingest.py` · `web/app/plaza/`。

- **DEC-036**（owner 2026-08-08 裁决 · 主题名称三元组：改规格，不动冻结件）：冻结件 `contracts/models.py#Topic` 的全部字段是 `topic_id / seed_id / one_liner / target_user_tag / form_factor_tag / why_now / keyword_mapping / embedding`——**它本来就没有名称**。而规格 `#2.4` 写着「名称三元组上屏：主行 `name_native`，机翻译名为次要行」。**那一句大概率是从热点簇那边抄过来的**（簇确实有三元组，`HotspotCard` 正在用）。**改规格比动冻结件便宜得多，而且它才是对的**：给 `Topic` 加两个没人产出的字段，只会让屏上出现一个「永远没有译名的三元组」——那看起来像翻译服务坏了，而真相是这个实体从来就没有名称。`SPEC-01` 顺带建一条判据：**规格里凡提名称三元组的实体，冻结件里 MUST 真有那两个字段**——下一次抄错会被当场拦住。影响面：`docs/前端功能说明-v2.md#2.4` · 新判据 · 关闭 `docs/blocked/TOPIC-HAS-NO-NAME-TRIPLE.md`。

- **DEC-037**（owner 2026-08-08 裁决 · 那条红：改取证样例，不改产品）：`/jobs/m1004-j` 回 **403** 是第 4 批鉴权接上之后的**正确行为**——那条作业的发起人不是探针用的 `self`，屏上也正确地显示「无权查看」。**红的是取证样例**：样例 id 是鉴权之前从库里查出来的，鉴权落地后没跟着对齐。`FIX-09` 给探针**种一条属于它的作业**。**NEVER 把 403 加进控制台噪声白名单**——那等于**把鉴权正确工作的证据当成噪声吞掉**，而下一次鉴权真的坏了时，这条判据不会响。同卡另建一条判据专门守「无权时屏上显示无权查看」，让这条正确行为**从此有人量**。影响面：`harness/fe_smoke.py` 的 `SAMPLE_IDS` · 种子数据 · `tests/v041/test_sse_live.py` · 关闭 `docs/blocked/DEMO-JOB-NOT-OWNED-BY-THE-PROBE-USER.md`。

- **DEC-038**（owner 2026-08-08 裁决 · 维持 `DEC-034`）：Gate 四分类**不借** `_ds` 已经有主的八态记号。`D_insufficient → void`（证据不足 = 有形空缺，**语义逐字相同**），其余三类 → `verified`，**分类本身由标签文字承载**。理由采纳 worker 写的那一句：**借一个已经有主的记号去说另一件事，比不给记号更坏**——`disputed` 在本仓是铁律级的事实状态（`S2-4`：`status=="disputed"` 的 fact NEVER 被新生成引用），拿它去表示「红海赛道」，屏上「这条结论有争议」与「这个赛道是红海」就共用一个记号。**代价照它自己说的记下**：A/B/C 三类在记号上看起来一样，比素材少一层可扫性。**要四档各有各的记号，那是给 `_ds` 加记号（动供应商资产，终检 C6 的口径），不是借现成的——本批不做。** 影响面：`web/components/hotspot-card/verdictStatus.ts` 维持现状，不改。

- **DEC-039**（owner 2026-08-08 裁决 · 热点卡的陈旧槽恒不显示，走 `SLOT-02` 单的甲）：`SLOT-02` 停得对，而且它的理由比「做不了」强得多——**热点簇不是一份分析：它不引用事实，它本身就是事实的来源之一**。`Revalidator` 判的是「一份分析引用过的事实变没变」，需要 `project_id`、账本版本、被引用的那些事实三样，而 `clusters` 表一样都没有；全库带 stale 语义的只有 `deliverables.stale_reasons` 与 `pricebook.stale_after_months`，**没有第三处**。唯一能挂到簇上的是 `Favorite.snapshot_stale`，它说的是「**你收藏的那份快照旧了**」，印在广场卡上会被读成「**这个热点旧了**」——两句话不是一回事（与 `DEC-038` 同一形状）。今天也借不到：`fav/store.py:35` 自述是内存实现，`favorites` 表不存在，标记每次重起就消失。**本条真正的产品是那条禁令，不是「把槽藏起来」这个动作**：**全仓 NEVER 用 `last_active` 或 `first_seen` 做算术得出「陈旧」**（形如 `now - last_active > N`）——那是新写一套比对，**而且它说的是系统不知道的事**。影响面：`STALE-01` 建禁令判据并让槽恒不显示 · 关闭 `docs/blocked/SLOT-02-A-CLUSTER-HAS-NOTHING-THE-REVALIDATOR-CAN-JUDGE.md`。

- **DEC-040**（owner 2026-08-08 裁决 · `global` 与 `NULL` 归入显式的「未归区」）：steward 实查的分布是 `global = 103`、`CN = 89`、`NULL = 1`。`global` 是 `ghtrend` 写死的常量，**不是地理事实**——把它当第九区，用户会在地理列表里选到一个不存在的地方；让它从筛选面消失，那 104 条在默认视图之外**再也看不见**。**「未归区」是唯一诚实的说法**。合并**只发生在呈现层**：库里 `NULL` 与 `global` 保持可分辨，**NEVER 把 `NULL` 回填成 `global`**——那会抹掉「这条簇从来没归过区」这个事实，**而抹掉之后，抹掉本身也看不见了**：回填过的行与本来就是 `global` 的行长得一模一样。影响面：`REGION-11` 在呈现层加未归区选项 · `flint/api/views.py` 的 region 查询与 `_known_regions()` · `web/app/plaza/page.tsx` 的地区切换 · 关闭 `docs/blocked/REGION-08-GLOBAL-IS-A-SOURCE-CONSTANT-NOT-A-REGION.md`。

- **DEC-041**（owner 2026-08-08 裁决 · demo 库种一条主题，走 `DEMO-TOPIC` 单的甲）：主题两屏（`/projects/{id}/topics` 与 `/topics/{id}`）至今没有真数据可看，取证样例 id 是个占位符。种一条进 demo 库，让这两屏第一次有东西；它与「广场数据是合成的」同族，而那一族已经被接受，**本条不新增性质**。**种的是夹具**：id 与文案都前缀标出它是夹具，**NEVER 冒充模型产出**；种子恒幂等。**判据有一条硬的**：种完之后把 `CONSOLE_BASELINE` 里为 `/topics/[id]` 留的那条 `404` 额度**撤掉**，撤掉后仍绿才算数——不撤的话额度还在，屏上哪天再退回 404 时**没有一条判据会响**。影响面：`SEED-01` 种子脚本 · `harness/fe_smoke.py` 的 `SAMPLE_IDS` · `CONSOLE_BASELINE` 的 `/topics/[id]` 额度 · 关闭 `docs/blocked/DEMO-TOPIC-SAMPLE-ID-IS-A-PLACEHOLDER.md`。

- **DEC-042**（owner 2026-08-09 裁决 · 卡片点击的去向）：owner 亲自点过界面之后的原话——「**点卡片进入卡片的分析界面，要使用卡片才进入图谱工作台**」。逐条落地：**① 卡片主体是导航**，点它进入这个热点的**分析界面**；**② 三个动作按钮（收藏 / 入台 / 分享）是动作**，其中**「入台」才把人带去图谱工作台**。**两者 NEVER 混为一谈**——`HOTSPOT-02` 的**点击排除区**判据正为此而建：混起来之后，用户想收藏、手指落在按钮旁边一点，屏就整个跳走了，而他并不知道自己刚才导航去了哪。**③ 打开分析界面只是查看，NEVER 顺手跑一次分析**（`web/views/analysis/AnalysisView.tsx` 文件头原话）：那会让用户每次点开都**付一次钱**，且同一个热点可能每次显示不同的判定——**判定本身就不再可被引用**，而「结论必有引用」是这套系统的第一条铁律。**这条走法接得上已有的件**：`AnalysisView` 是 `HOTSPOT-03` 建的成品（四态齐全、只读、复用 `viewsClient`），而**全仓没有任何屏在用它**——缺的只是一个承载屏。影响面：`NAV-02` 给它建承载屏 · `NAV-03` 让「入台」成功后带人去图谱工作台 · `web/components/plaza/PlazaCards.tsx` 的网格项接线 · `web/components/hotspot-card-actions/HotspotCardActions.tsx` 的排除区维持不变。

- **DEC-043**（owner 2026-08-09 裁决 · 主链路的活入口）：owner 的原话——「**先把所有要做的都做了，然后把功能全部接通，后面我才能对着产品一步一步修改**」。第 8 批 `NAV-05` 之后，项目族六屏**内部已经连通**，缺的只是走进这一族的第一步（单据 `docs/blocked/MAIN-CHAIN-HAS-NO-LIVE-ENTRANCE.md`）。两条路摆在面前：**甲**——广场多选卡片建组合（`POST /projects/combo` **端点早就装配好了**，缺的只是入口）；**乙**——分析界面直接建项目（更短）。**裁决取甲**，理由是「**多个热点凑一个假设**」正是本产品与普通热榜的分界：乙案绕开了「组合」这个产品概念，用户建出来的项目只挂着一个热点，而这套系统的证据卡、竞品强度、Coverage 全是按「一组热点支撑一个假设」设计的。影响面：`ENTRY-04` 在广场加多选与「用选中的卡建组合」 · `ENTRY-05` 据此把孤岛清零 · `/combo` 屏本身一行不用改（它按 `?cluster=` 取证据卡的行为原样保留）。

- **DEC-044**（owner 2026-08-09 裁决 · cluster→判定落成持久化真相）：`DEC-012` 当初记的乙案。**不做它，热点分析屏对每一个热点永远只会说「还没有过 Gate① 判定」**——而那正是 owner 刚点进去看的那一屏。今天的实况：判定按 **job** 键落在 `snapshots['snap-{job}-verdict']`，`Job` 无 `cluster` 字段、`jobs` 表也无 `cluster_id`，所以从一个热点出发**无从查起**（`docs/blocked/HOTSPOT-03.md` 记的就是这件事）。落法上有一条硬的：**`contracts/` 一字不动**——`Job` 无 `cluster` 字段这件事保持原样，对应关系**落在关系表里**。读法上，**猜 job id 那条路一并删掉**：在此之前「缺就是缺」是唯一诚实的做法（拼一个去试，猜错时用户看到的是**另一个热点的判定**并会把它引进计划书），而**现在有真相可查了**，再猜就不是诚实而是偷懒。一个热点多次判定时**取最新一条**（steward 在卡面上定的默认，owner 可改口径）。影响面：`ENTRY-07` 建关系表与读法 · 热点分析屏的 `verdictJobId` 改为可从这条真相查出 · `DEC-012` 那句「由调用方持有」在**有真相可查**的场合退居次位，调用方显式给出时仍然优先。

- **DEC-045**（owner 2026-08-09 裁决 · 本版只做中国区，多源多区推迟下一版）：owner 原话——「**不同地区不同信息源的问题下一个版本再解决。这个版本，先把所有接口接上，先做中国区的内容**」。**推迟的是「不同地区用不同信息源」这一件，不是「地区」这个功能**：`REGION-08~12` 建的九区列、query 与分列**一律保留不拆**，本版做的是**收窄呈现**——**NEVER 删代码**。其余八区与未归区**保留在筛选器里，并如实说明本版暂无该区内容**，**NEVER 悄悄隐藏**：隐藏之后用户**不知道这个能力存在**，而它**下一版就要用**；而且「本版暂无该区内容」「查过了是空的」「读失败」是**三态**，混成一个之后谁也说不出屏上那一片空白是哪一种。推迟本身要落成**机读记录**（形如 `legal_policy` 的 `RECORD_ONLY`），触发条件写成「下一版」，NEVER 只留在对话里。**执行边界**：本版中国区的内容要成为**真实热点**而不是 `fixtures/weibo/*.json` 的合成词面，而换成真的就是**真实源抓取**——`CN-01` 是**红线卡**。`DEC-022`（2026-08-04）授权的是 B 档抓取的**纪律形态**（抓完必录 `fixtures/`），欠的是**首次实跑需 owner 在场点一次**（`docs/blocked/E2E-REALSOURCE.md` 的原话），两者是两件事：写成「已授权」的话，下一个会话会直接去跑，而那正是 owner 保留给自己的那一次点头。影响面：`CN-02` 收窄呈现并落机读记录 · `CN-01` 准备到位后停下等 owner · `flint/api/views.py` 的默认区 · `web/app/plaza/` 的筛选器话术。

- **DEC-046**（owner 2026-08-09 裁决 · 地区与语言下拉挪到右上角）：owner 原话——「**地区和语言做到页面右上角，直接下拉选择**」。实况：`LocaleSettings` 只挂在 `/settings/locale` 那一屏，`RegionSwitch` 另有一个实例挂在广场页上，**外壳右上角两者都没有**。落法：右上角加两个下拉，**复用既有件**（`RegionSwitch` 与 `LocaleSettings` 的取值与写回口径 NEVER 另写一份，九区清单仍从 `GET /settings/locale` 的 `options` 取），`/settings/locale` **保留为详情屏**。真正的约束不是「挪个位置」，而是**两条轴各自独立**（`PRINCIPLES#A3`）：**切地区 NEVER 改语言，切语言 NEVER 改热点集合**。挪位置这个动作最容易顺手把两者并成一个「区域设置」控件——并了之后，**一个说中文的人想看美国区的热点就没法表达了**。第二条硬的是**两处显示同一个值**：各存一份的话，用户在右上角切了区、进详情屏看到的还是旧的，而**两个真相长得一模一样**，谁也说不出哪个是对的。选择 MUST **存得住**——刷新后仍是上次选的，靠 `prefs` 表（`PERSIST-01` 建），**NEVER 只存在内存里**。影响面：`SHELL-01` 实现右上角两个下拉 · `PERSIST-01` 建 `prefs` 表 · `FIX-05/06` 的 390px 顶栏不溢出判据不倒。

- **DEC-047**（owner 2026-08-09 裁决 · 补白天/夜间切换）：owner 原话——「**白天夜间的功能还没有做**」。实况分两层：`DARK-01` **早就建好了暗色板与双通道**（`prefers-color-scheme` 与 `data-theme`，后者压过前者，见 `web/public/_ds/.../tokens/colors.css`），**缺的只是控件**——`web/`（`DEC-007`/`DEC-026` 定的唯一前端工程根）下 `data-theme` / `toggleTheme` / `ThemeToggle` 零命中，所以今天用户只能跟着系统偏好走，手动切不了。**「零命中」的范围 MUST 写准是 `web/`**：`V0 files 前端设计/components/theme-toggle.tsx` 里**是有**一个 `ThemeToggle` 的，那是 `DEC-026` 划的**视觉蓝本**、NEVER 当工程目录——把范围写成「全仓」的话，下一个人 grep 一次就会以为这条裁决的前提是假的，进而怀疑整条裁决，而**说过头的真话与假话一样会被推翻**。落成**三态：跟随系统 / 白天 / 夜间**，**「跟随系统」MUST 是一个显式选项**（steward 2026-08-09 加的口径，owner 可当场划掉）：两态会把「**我没选过**」和「我选了白天」**混成一个**——前者在系统切暗时该跟着变暗，后者 NEVER 变，合并之后这两种人只能有一种被满足，而**屏上看不出自己是哪一种**。选择同样靠 `prefs` 表存得住；首帧 NEVER 闪白再变暗。影响面：`SHELL-02` 加控件 · `PERSIST-01` 的 `prefs` 表 · `DARK-02` 的 `theme-switches` 判据不倒（两主题量到同一组颜色仍判红）· `web/app/globals.css` 文件头那句「`_ds` 目前只有一套明色」是 `DARK-01` 之前写的，已经过期，由 `SHELL-02` 一并订正。

- **DEC-048**（owner 2026-08-09 裁决 · 八张缺表一次建齐）：owner 原话——「**收藏、入台、固化这些都没提供接口**」。**根因不在接线那一层**：steward 实查 `pg_tables`（worker 用 `asyncpg` 复核，库里 38 张表）——`favorites` · `share_links` · `prefs` · `templates` · `workbenches` · `graph_nodes` · `graph_edges` · `cluster_verdicts` **八张一张都不存在**。所以屏上那些 `not_provided` 是**持久层从没建**，**不是接线没做**：`flint/fav/store.py:35` 自述「内存实现；SQL 实现随 E2 的 `favorites` 表接入」，那个接入一直没做；`POST /workbenches` 前端早就接完了，实测回框架 404，**入台永远拿不到 `ok`**；`templates` 表没有，所以「固化为模板」恒置灰，`flint/jobs/dispatch.py` 的 `UnwiredKindReason` 只剩 `template_solidify` 一条；`cluster_verdicts` 表没有，所以热点分析屏对每一个热点永远只会说「还没有过 Gate① 判定」——**owner 刚点进去看的就是这一屏**。写成「接口没接上」的话，下一个人会去前端找断线，而前端没有断线。落法：四张迁移卡一次建齐，迁移号从 `0023` 起顺序编，**NEVER 跳号也 NEVER 撞号**，每张的 `upgrade` 与 `downgrade` 都跑通；`not_provided` 那一态**保留但不再触发**——「查过了是空的」与「没查过」NEVER 再合并。影响面：`PERSIST-01`（收藏/分享/偏好）· `PERSIST-02`（工作台三表 + `POST /workbenches`）· `PERSIST-03`（模板表 + `template_solidify`）· `PERSIST-04`（cluster→判定关系表，落 `DEC-044`）。

- **DEC-049**（owner 2026-08-09 裁决 · 活入口走甲的落地口径）：这一条是 **`DEC-043` 的落地口径，不是一条新裁决**——`DEC-043` 定的是**走甲**（广场多选卡片建组合，而不是分析界面直接建项目），`DEC-049` 定的是**甲怎么落**。两者互相点名，为的是下一个人 NEVER 把它当成同一件事记了两遍然后删掉一条：**两条的影响面并不相同**（`DEC-043` 约束的是产品概念上的取舍，`DEC-049` 约束的是那个入口长什么样）。落法：广场加**多选态**，选中两张或更多卡片之后「用选中的卡建组合」入口出现，进 `/combo` 并带上所选 `card_ids`；`POST /projects/combo` **端点早就装配好了**（`flint/api/combo.py`），缺的只是这个入口。**多选 NEVER 干扰既有单击**：点卡片主体仍进热点分析（`DEC-042`），多选走独立的选择控件，两者各有判据。**这一步就是 6 座孤岛的入口**——项目族六屏在第 8 批 `NAV-05` 之后内部已经连通，缺的只是走进这一族的第一步（`docs/blocked/MAIN-CHAIN-HAS-NO-LIVE-ENTRANCE.md`），**NEVER 用假链接顶替**：假链接会让可达性尺子转绿而人仍然走不进去，那比红着更坏。影响面：`ENTRY-04` 在广场加多选与建组合入口 · `ENTRY-05` 据此把孤岛清零 · `/combo` 屏本身一行不用改。

- **DEC-050**（owner 2026-08-09 裁决 · `SHELL-02` 的 outputs 扩两处，主题存服务端）：`SHELL-02` 的 acceptance④ 要「刷新后仍是上次选的（`prefs` 表）」，而卡面 outputs 只有 `web/components/shell/` 与判据文件；存主题要动 `migrations/`（`prefs` 加 `theme` 列）、`flint/profile/prefs.py`（第三根轴）、`flint/api/settings.py`（端点认它）——**三处都在 outputs 之外**。worker 按本批 rules 停下开单、**一行代码都没写**，owner 原话：「**那是对的行为**」。**裁决**：`SHELL-02` 的 outputs **增加 `migrations/` 与 `flint/`**（`profile/prefs.py` + `api/settings.py` 两处）。主题作为**第三根正交轴**存进 `prefs` 表，与 `lang` / `region` 同一套读写口径。迁移**接盘上当时最高的那一号，不留号也不跳号**（`0025` 已被占，理由见 `docs/trace/PERSIST-03.md` §2）。**为什么不按设备存**（owner 原话，逐字）：`DEC-047` 与 `SHELL-01` 的判据都写死「服务端为真相」。而「夜里用手机、白天用台式机想要的不一样」这个真实需求，**三态里的「跟随系统」已经覆盖了**——选「跟随系统」的人，每台设备各跟各的系统走；显式选了亮或暗的人，是在说「我到哪都要这个」。所以主题**不单开一套按设备的存法**。影响面：`prefs` 表加一列 · `Prefs` 加一个字段 + 越界值校验 · `GET/PUT /settings/locale` 认第三根轴（`extra="forbid"` 照旧，只是多认一个合法键）· 右上角三态控件。另五条 acceptance（三态 / 「跟随系统」是显式选项 / 显式选择压过系统偏好 / `DARK-02` 的 `theme-switches` 不倒 / 首帧不闪白）与 outputs 无冲突，一次做完。

- **DEC-051**（owner 2026-08-09 裁决 · 仓里那两个「工作台」是两件事，`workbenches` 归入台那条路）：`DEC-048` 要建的 `workbenches` 撞上一个歧义——**甲** = `POST /workbenches`（`ENTRY-03` 建、前端在用）只知道**谁 / 哪个热点 / 什么时候**；**乙** = `WorkbenchGraph`（`contracts_v04/models_v04.py`，冻结加件）要 `project_id` 与 `title` **两个必填**。用户是在广场上点一张热点卡的「入台」，**那时他还没有建任何项目**，所以甲填不出 `project_id`。steward 已核真件：`flint/api/workbenches.py` 全文只拿 `x-user-id` + `seed_cluster_id` + `now`，`WorkbenchGraph` 那两个字段逐字必填——worker 的现象描述属实。**裁决：走第三条——两个概念分家。** `workbenches`（本卡建）＝ 甲：`graph_id` PK · `owner_id` · `seed_cluster_id` · `created_at`，**与 `WorkbenchGraph` 无关**，语义 =「**一个热点起一张思考图**」，无项目；`workbench_graphs`（**本批不建**）＝ 乙：`WorkbenchGraph` 逐字段落表，语义 =「**一个项目下的多张台**」（owner 原话在这里用了一个 `S2-8` 列为禁用词的量词，改写成不含糊的说法，意思一字未变），等 `K6` 的交互稿与 flag 打开时再建。**冻结件一字不动——这正是选它的理由**：另外两条路一条要**凭空造一段项目关系**（造出来的行与真的长得一模一样），一条要改冻结件（`S2-1` 判死的动作）。**代价**（owner 要求写进本条）：「我的工作台列表」**将来会有两个来源**，合并口径（同一个 `graph_id` 会不会同时出现在两张表里）**今天没有答案**，到 `K6` 交互稿落地时**必须回来定一次，NEVER 到那时才发现**。**再加一列**：`workbenches` 加 `project_id text NULL`，语义**逐字写死在迁移注释里**——`NULL` =「这张图还没有归属任何项目」，且 **NEVER 往这一列写一个编出来的项目 id**。理由：将来「把这张台挂进某个项目」是**一次 UPDATE，不是一次带回填的迁移**；而回填那天人手上没有真项目 id，**最可能做的事就是编一个**——那正是本条要防的。影响面：`PERSIST-02`（`-a` 存储 / `-b` 读端点与屏**两半一起解阻**）· 迁移接盘上当时最高的那一号 · 顺带纠正卡面两处（`frontend_wants_missing_backend` **实测 0 不是 1**，真正的缺口是 `frontend_untyped_response = 2`；acceptance④ 的 `GET /workbenches/{id}` **今天不存在**，是**新建端点 + 前端类型 + 屏接线**，不是接线）。

- **DEC-052**（owner 2026-08-10 裁决 · 真实源联网工作窗口）：**以下为 owner 粘贴的原文，一字未改**（来源 `docs/steward/起跑令-v041-第10批-2026-08-10-v2.md` 第 24–50 行）。落地时**只做了一件事：把它原样搬进来**——授权书里被改写过的句子，与原句之间的差别恰恰是「能做什么」与「不能做什么」的差别，所以这一条 NEVER 复述、NEVER 摘要。

```
【零】DEC-052（owner 2026-08-10）：真实源联网工作窗口 —— 首卡把它逐字落进 DECISIONS-v04.md

来由：CN-01 首次实跑（owner 在场，2026-08-09 UTC）两源全败——weibo 302（重定向弹走，
适配器无 UA 不跟随重定向）、gtrends 404（dailytrends 端点已被 Google 下线）。
机制无错（守卫/限速/错误分类/回执/零半成品/降级显示全按设计走），败在源契约：
四个适配器全部按合成夹具建，从没碰过真实站点——K1-02 预言成真。
owner 决定：给工作 AI 联网权限，联网事项一次解决。

裁决：授权本批 CN-04 / CN-05 / CN-06 三卡的真实网络工作，边界逐字执行——
· 域名族只许四源本家：weibo 族（s.weibo.com / weibo.com / m.weibo.cn 及其跳转目标）、
  trends.google.com、github.com、arxiv.org 与 export.arxiv.org；
· 请求额度：CN-04 调试每源每日 ≤20；CN-05 探测每源 ≤10；CN-06 完整录制一次
  （失败源当日补跑合并计入上述额度）；
· 每次探测往返 MUST 落 fixtures/_probe/{source}/（url / status / 关键响应头 /
  body 前 2048 字节 / UTC 时间戳）；正式录制走既有「抓完必录」：fixtures + provenance
  manifest + robots 快照，三样缺一即 fail；
· 开关一律命令行 flag，NEVER 环境变量；NEVER 登录凭据、NEVER 付费 API、
  NEVER 第三方聚合中转；免登录路全都要凭据时停下开单报 owner；
· 合规照 K2-01 RECORD_ONLY：照实记录、不阻断、NEVER 重判；
· **CN-06 那一次端到端真实录制由本裁决预授权**——「修完停下等 owner 点」改成
  「修完即跑、抓完必录、回执留档」；录制器为此新增 --authorized-by=DEC-052 旗标，
  NEVER 冒用 --owner-is-here（那个旗标的语义是「owner 此刻在场」，一字不动）；
· **每日定时的持续真实采集不在本裁决内**——那是上线动作，另行裁决；
· CI 照旧 NEVER 联网（S2-7）：一切判据走录制回放，联网只发生在 worker 手动执行的
  探测与录制命令里。

执行指令：DEC-052-LANDING 是本批第一张卡；CN-04/05/06 在它落地之前一个真实请求都不许发。
```

  **影响面**：`DEC-052-LANDING`（本条落地）· `CN-04`（weibo 302 / gtrends 404 修复，调试窗口每源每日 ≤20）· `CN-05`（ghtrend / arxiv 契约验证，每源 ≤10）· `CN-06`（端到端真实录制一次，**由本条预授权**，走 `--authorized-by=DEC-052`）。`CN-01` **不在本条授权内**——它是红线卡，那一次点头仍然只在 owner 手上。`worker.md` §4.3⑤「NEVER 动用真实网络」与本仓 rules 里同义的那句，在这三张卡的边界内由本条**定点解除**，边界之外一字未动；`S2-7`（CI 恒不联网）**不受影响**——判据仍然全部走录制回放，联网只发生在 worker 手动执行的探测与录制命令里。

- **DEC-053**（owner 2026-08-10 裁决 · weibo 走新浪访客系统匿名握手）：**以下为 owner 粘贴的原文，一字未改**。与 `DEC-052` 同一条纪律：授权书 NEVER 复述、NEVER 摘要——被改写过的句子与原句之间的差别，恰恰是「能做什么」与「不能做什么」的差别。

```
【DEC-053（2026-08-10，owner）：weibo 通道走新浪访客系统匿名握手】

来由：CN-04 探测（DEC-052 窗口内，weibo 5/20 留痕）证实五条免登录路全废——
s.weibo.com 与 m.weibo.cn 全 302 到访客系统，weibo.com 两条 ajax 全 403；
CN-01 那个 302 与跟不跟随重定向无关。唯一免费路 = 访客系统匿名握手（两次 POST 拿访客 cookie）。

裁决：授权实现。它不是账号登录（无用户名密码，任何浏览器匿名访问时自动做同一件事）。
owner 知悉并接受两条真实代价：①反爬对抗件会碎——碎了广场如实降级，本版没有推送告警；
②平台条款风险由 owner 承担（合规照 K2-01 RECORD_ONLY 照记，上线前合规清单已有微博项）。

边界（逐字执行）：cookie 值 MUST 每次动态获取，NEVER 硬编任何一枚；
浏览器指纹参数集中一处、文件头注明「上游对抗件，预期会碎」；
握手与抓取失败如实 DegradationNote，当日补跑 NEVER 超 DEC-052 额度；
授权上限就是访客握手——NEVER 升级成账号登录或引入任何凭据，要更多回来找 owner。
```

  **影响面**：`CN-04` 的 weibo 半解阻（`flint/sources/weibo.py` 重建取数路）· `CN-06` 端到端录制 · `fixtures/_record_cn_real.py`。**worker 上一轮开的单 `CN-04-WEIBO-ALL-ANONYMOUS-ROUTES-NEED-A-VISITOR-COOKIE.md` 由本条答复并关闭**——worker 当时倾向「这一版先不要 weibo」，owner 选了另一条并**明写接受两条代价**（对抗件会碎、平台条款风险由 owner 承担）：这两句是本条与「悄悄做了」的分界线，NEVER 在转述里省掉。

- **DEC-054**（owner 2026-08-10 裁决 · gtrends 本版走港区代理口径）：**以下为 owner 粘贴的原文，一字未改**。

```
【DEC-054（2026-08-10，owner）：gtrends 本版走港区代理口径】

来由：CN-04 探测（gtrends 7/20 留痕）证实旧 dailytrends 已下线；新 trending/rss 活着
（US/HK/TW 全 200）但 geo=CN 回 400——Google 不编大陆榜，这是上游边界不是适配器缺陷，
换任何客户端都变不出来。owner 决定不放弃这个源。

裁决：采集 geo=HK 的 trending RSS，region 落 CN。这是产品口径不是数据谎言——
「本版中国区」的 Google 信号定义为华语圈港区榜代理。诚实性由三件东西扛，缺一即 review_failed：
①本条 DEC 文本明写代理；②provenance manifest 记真实 geo=HK 的 URL；
③屏上署名 MUST 显示「Google 趋势（港区）」（复用 FIX-17 的 sourceName 机制，
判据取渲染后可见文本——你原来拒的是无标注冒充，署名上屏后那个反对不成立了）。

另两条：ht:approx_traffic 是区间下界（形如 200+），score 照实存下界 NEVER 编精确值；
下一版做多区时本代理口径撤销、改真区——这句一并写进 DEC。
```

  **影响面**：`CN-04` 的 gtrends 半解阻（`flint/sources/gtrends.py` 换端点重建解析）· `CN-06` 的广场出口（CN 区 = weibo 真实大陆热搜 + 「Google 趋势（港区）」署名条目）· provenance manifest · 前端 `sourceName`（`FIX-17` 建的那套机制）。**单据 `CN-04-GTRENDS-HAS-NO-CHINA-REGION.md` 由本条答复并关闭**。**这是本仓唯一一处「采集地区与呈现地区不同」**，所以它的诚实性不靠一句承诺、靠三件同时在场的东西（DEC 文本 · manifest 里的真实 URL · 屏上那行署名）；掉任何一件，屏上就变成「港区的榜冒充大陆热点」——那正是 worker 上一轮拒绝的形状，而 owner 的答复是**把标注做上屏**，不是**取消标注**。退出条件写死在原文里：**下一版做多区时本代理口径撤销、改真区**。

- **DEC-055**（owner 2026-08-10 裁决 · 收藏的证据快照由后端自取）：**以下为 owner 粘贴的原文，一字未改**。

```
DEC-055（2026-08-10，owner）

收藏的证据快照由后端在收藏那一刻自取。

来由：POST /favorites 的 evidence_snapshot 必填，而广场那个动作手上只有热点卡面
（cluster_id / 名称 / 热度），拼不出真快照——前端拼一份就是编一份证据
（FAV-WRITES acceptance④ 逐字禁止）。于是从广场收的每一条，屏上都说「内容不在了」：
那句是实话，而真相是没有人往里面放东西。

裁决：evidence_snapshot 从必填改成可选；前端只发 target_kind / target_id，
后端按它自取当刻的证据卡组一份内嵌快照。冻结件 Favorite 的「内嵌不引用」语义一字不动
（它防的是被引 snapshot 被周删清掉后收藏变成空壳）——改的是谁来放，不是放什么。

边界：取不到证据卡时 NEVER 存空快照冒充成功——照实失败并让屏上说清是取证失败，
NEVER 与「内容已被清理」共用同一句话（两者该让用户做的事完全不同）。
```

  **影响面**：`FAV-SNAPSHOT`（`FavoriteCreate.evidence_snapshot` 改可选 + 后端自取 + 取证失败与内容已清理两句分开）· `web/components/plaza/cardActions.ts`（不再送 `{}`）· `docs/blocked/FAV-SNAPSHOT-HAS-NO-PROVIDER.md` 由那张卡关闭。**冻结件 `Favorite` 一字不动**——本条改的是谁来放，不是放什么。

- **DEC-056**（owner 2026-08-10 裁决 · CN 与 HK 两区分家）：**以下为 owner 粘贴的原文，一字未改**。

```
DEC-056（2026-08-10，owner）

CN 与 HK 两区分家，各自一源：CN = 微博热搜，HK = Google 趋势。两区都可切。

来由：CN-04 探明 Google 不编大陆榜（geo=CN 回 400），DEC-054 因此让 HK 数据以
「华语圈代理」的名义落 CN 区并在屏上署名「Google 趋势（港区）」。owner 2026-08-10 判断
两区分开更清晰，且今天两源各自的地域归属本来就不同。

本条修订 DEC-045：DEC-045 写的是「本版只做中国区；不同地区用不同信息源推迟下一版」。
现在提前执行后半句——本版做 CN 与 HK 两区，各用各的源。DEC-045 的其余部分（默认区为 CN、
其余七区明说「本版暂无该区内容」）继续有效。

本条触发 DEC-054 自己写下的退出条件：「下一版做多区时本代理口径撤销、改真区」。
代理口径就此撤销——gtrends 的 region 从 CN 改为 HK，署名与出处链照旧全真。

裁决：
· gtrends 采集的 EMIT_REGION 从 CN 改为 HK（FETCH_GEO 本来就是 HK；CN-04 把这两个常量
  刻意分开正是为了今天这一改，NEVER 把它们合起来）；
· CN 区 = 微博，HK 区 = Google 趋势，两区都进「本版有内容」的范围；其余七区照旧明说
  「本版暂无该区内容」，CN-02 那三句不同的空态一条都 NEVER 合并；
· 库里既有的 gtrends 行今天标着 region='CN'，而其 provenance manifest 记的是真实的
  geo=HK URL——回填是把标签改回与出处一致，不是改写事实，这句要写进迁移注释；
· provenance 的真实 URL、库里的 region、屏上的署名三者 MUST 一致，各有判据；
· 后果照实说：CN 区卡片数会从 60 掉到 50（10 条港区条目移去 HK 区）——不是数据丢了，
  是分家的必然结果；
· 其余七区 NEVER 顺手打开，那是下一版的事。
```

  **影响面**：`REGION-CN-HK`（`flint/sources/gtrends.py#EMIT_REGION` CN→HK · 迁移回填既有 gtrends 行的 `region` · 广场两区都可切 · 署名去掉「（港区）」那个补丁——它当初是代理口径的第三条腿，两区分家之后 HK 区本身就说明了地域）· `assets/` 的地区清单口径。
  **这一条同时是两次回改的落点，而 `DECISIONS-v04.md` 是 append-only**：
  `DEC-045`（本版只做中国区）与 `DEC-054`（港区代理口径）的行**一个字都没有动**，
  「它们被改了」这件事**只由本条单向声明**。读那两条的人顺着编号找得到这里——
  这是本仓处理「回改」的唯一形态：**NEVER 回头改一行，永远向前加一条并点名它改了谁**。
  `DEC-054` 的退出条件（「下一版做多区时本代理口径撤销」）由本条**点名触发**——
  一条临时口径最容易的死法不是被违反，是**没有人记得去撤销它**。

- **DEC-057**（owner 2026-08-11 裁决 · Gate① 真实分析的网络授权窗口）：**以下为 owner 粘贴的原文，一字未改**。

```
DEC-057（2026-08-11，owner）

Gate① 真实分析的网络授权窗口。

来由：第 11 批把「判定 → 落库」那条链修好并离线验过 13 条判据，而 cluster_verdicts
今天仍是 0 行——差的只是一次真跑，而真分析要打真实网络（证据检索），属事前必审。

裁决：授权一次端到端的真实分析跑通，边界逐字执行——
· 域名族只许证据检索的既有两家：github.com（含 api.github.com）与 arxiv.org / export.arxiv.org；
  NEVER 扩到任何其他站点；
· 额度：本次授权总共 ≤40 个真实请求（跨源合并计），跑不通就停下开单，NEVER 加码重试；
· 每次往返 MUST 落 fixtures/_probe/gate1/（url / status / 关键响应头 / body 前 2048 字节 /
  UTC 时间戳），与 DEC-052 同一套格式；
· 模型一律**免费本地档**（LocalProvider → 本机 Ollama），NEVER 读任何 API key、
  NEVER 调付费接口；
· 跑完 MUST 把真响应转成回放夹具，判据全部离线跑（CI 恒不联网，S2-7）；
· 本窗口**只授权这一次跑通**：跑通之后再要真实分析，回来找我。
  每日定时的持续真实分析 NEVER 顺手接上（与 DEC-052 同一条边界）。

出口：cluster_verdicts 至少多出一行、GET /clusters/{id}/verdict 取得回来、
分析屏显示的是判定而不是「还没有判定」，逐屏截图留 trace。
```

  **影响面**：`GATE1-REAL`（⑥热点分析的出口——第 11 批把链修好、离线验过 13 条判据，而 `cluster_verdicts` 仍是 0 行，差的只是这一跑）· `fixtures/_probe/gate1/` 留痕 · 由真响应转出的回放夹具。
  **这是第二个网络窗口**（第一个是 `DEC-052`，只覆盖 `CN-07`）。两者共用同一套边界形状：**域名族封闭 · 额度写死 · 每次往返留痕 · 跑完转夹具 · 只授权这一次**。第 11 批的 `VERDICT-01` 与 `SMOKE-01` 都因为不在 `DEC-052` 范围内而**只接线、不实跑**——本条把那一跑放行。
  「跑不通就停下开单，NEVER 加码重试」这一句是**额度纪律的核心**：40 个请求用完而没跑通时，多打一发不会让它变通，只会让下一次授权更难要。

- **DEC-058**（owner 2026-08-11 裁决 · 跨区簇走乙：源常量不参与定区）：**以下为 owner 粘贴的原文，一字未改**。

```
DEC-058（2026-08-11，owner）

跨区簇：走乙——不表达地理的源值不参与定区。

来由：c-20260629-108（脑机接口）的成员来自 ghtrend（region='global'）与 gtrends（HK），
region_of_members 按既有口径拒绝取众数并留 NULL。你倾向乙，我同意，理由是你写的那一句：
global 是 ghtrend 写死的源常量，web/lib/regions.ts 已明写「它不是地理事实」——
一个不表达地理的值参与定区，本来就说不通。

裁决：给 region_of_members 加一条规则——**源常量（今天只有 global）不参与定区**；
其余成员若指向同一个区，簇归那个区；其余成员仍跨真区时，
**既有口径原样保留：停下上报、NEVER 取众数**。

边界：
· 「哪些值是源常量」MUST 一处定义他处引用，NEVER 在 backfill 与前端各写一份；
· 全部成员都是源常量时 → 照旧 NULL（未归区），NEVER 硬挑一个区；
· 这条规则**放宽的是判定输入，不是判定纪律**——跨真区仍然停下，这句写进注释；
· 回填只处理今天这一条（实查全库混源簇 1 条），NEVER 顺手重算全库。
```

  **影响面**：`REGION-SPAN`（`flint/region/backfill.py#region_of_members` 加规则 + 回填 `c-20260629-108` 那一条）· 「哪些值是源常量」的一处真相（后端与 `web/lib/regions.ts#UNASSIGNED_REGION` 同款形态：一处定义、他处引用）。
  **本条放宽的是判定输入，不是判定纪律**——这是它与「取众数」的分界：取众数是**拿多数压掉少数**，而本条是**把一个本来就不表达地理的值排除在输入之外**。跨真区仍然停下上报，那句 owner 写进了边界，也要写进注释。
  **回填只动今天这一条**（实查全库混源簇 1 条）：顺手重算全库会把一次规则修订变成一次静默的批量改数，而那正是 `DEC-056` 的迁移注释在防的事（「回填是把标签改回与出处一致，不是改写事实」）。
- **DEC-059**（owner 2026-08-12 裁决 · 新增计划书主工作台，「AI 设计工作台」改名退居次要）：**以下为 owner 第 14 批工单【2】【3】两节原文，一字未改**。与前四条不同，owner 本批**未另贴** DEC 块（`DEC-055`~`DEC-058` 都是贴进来的独立文本），所以这里 NEVER 写「owner 粘贴的原文」那一句——那句话在这里会是假的，而**下一个人看到它就不会再回去核对措辞**。措辞要不要改由 owner 定，编号与裁决内容不受影响（`docs/blocked/DEC-059-TEXT-CAME-FROM-THE-WORK-ORDER.md`）。

```
DEC-059（2026-08-12，owner · 原文取自第 14 批工单【2】【3】两节）

【2 · owner 2026-08-12 的两条裁决】
· **新增主工作台**，不替换现有「AI 设计工作台」——后者改名退居次要，
  DESIGN-01~03 的端点/作业/固化流程一个字不改，成果一点不丢；
· **一批做完**：三栏骨架 + 卡片选取 + 对话生成 + 实时预览 + 章节导航 + 逐章检查 + 五模板切换，
  一次到位。

【3 · 本批最硬的一条，先读再动手】
蓝本让 LLM **直接吐 HTML**（<part id="…"> 包 <block type="…">，再用
html.match(new RegExp('<part id="' + sid + '">…')) 正则抠回来）——
**因为它是一个没有后端的独立 demo**。

本仓 NEVER 这样做：Block 是冻结件里的判别联合，带 claim_ids / fact_ids / 三通道 /
提升不变量 / 渲染门禁；照蓝本那套实现会把这些**全部绕过去**。

· 生成 MUST 走既有 compose 真链（flint/jobs/compose.py + build_production_compose_deps）产真 Block；
· 判据 MUST 断言：**全仓没有任何一处用正则从 LLM 输出里抠 <block 或 <part**；
· 蓝本的**视觉与交互**照做，**数据走真链**——两者不冲突：
  蓝本的 block 类型与本仓 Block 联合基本一致，连「资料不足绝不注水、改出 gap_notice
  并写明缺什么与该找哪些来源」都与三条铁律同构。
```

  **影响面**：`WB-01`~`WB-06`（新一屏：三栏骨架 / 左栏卡片选取 / 中栏对话生成 / 右栏实时预览 / 章节导航与逐章检查 / 五模板切换与单块批注）· `WB-07`（旧屏改名退居次要）· `EYE-05`（看屏取证）· 蓝本 `前端设计/ai工作台/Flint 设计台 v3.dc.html` · 新增导航项「工作台」（既有 6 个入口一个不改）。
  **「新增」与「替换」的差别是可以被数出来的**：`DESIGN-01~03` 做成的是 `/design` 那一族路由、design 家族的作业与固化流程。替换掉那一屏，这些会跟着一起消失，而**消失之后，消失本身也看不见了**——新屏跑得好好的，没有人会回头去数少了什么。所以 `WB-07` 只做**改名与排序**：那一屏的端点与作业一个字不改，且 **NEVER 把它从导航上摘掉**（摘掉就是把一个做完的能力藏起来，而藏起来与删掉在屏上长得一模一样）。
  **第三节是本批唯一一处「照蓝本做就会做错」的地方**：蓝本是个没有后端的独立 demo，它的 `parseDoc(html)` 用 `new RegExp('<part id="' + sid + '">…')` 把模型吐出的 HTML 抠成块。本仓照抄的话，`Block` 判别联合上挂着的全部约束（`claim_ids` / `fact_ids` / 三通道互不混用 / 提升不变量 / 渲染门禁）会被**整条绕开**——而绕开之后**屏上什么都不缺**：文档照样有章节、有段落、有引用样式，只是那些引用不再指向任何一条 `Fact`。所以这一条不靠自觉，靠一条**全仓判据**钉着（`WB-03`）。
  **蓝本与本仓同构的那一处也记下来**：蓝本的 `gap_notice`（资料不足时不注水，改出一块写明「缺什么、该找哪些来源」）与本仓三条铁律里的「结论必有引用」是同一件事的两种写法——**视觉照做而数据走真链，两者因此不冲突**。

- **DEC-060**（owner 2026-08-12 裁决 · 三条：v4 调色板并入 `_ds` / 保路由局部吸收 / 本轮出卡不直接改码）：**以下文字是 steward 拟的选项文本，owner 从三组选项里各选定一项**——**NEVER 写成「owner 原文」或「owner 粘贴的」**：那句话在这里会是假的，而下一个人看到它就不会再回去核对措辞。措辞要不要改由 owner 定，编号与裁决内容不受影响（同 `DEC-059` 的处置，开单 `docs/blocked/DEC-060-TEXT-IS-STEWARD-AUTHORED-OPTIONS.md`）。

```
DEC-060（2026-08-12，owner 裁决 · 三条）
出处：以下文字是 steward 拟的选项文本，owner 从三组选项里各选定一项。

一 · 调色板：把 v4 的值写进 _ds，唯一颜色来源不变。
  单一颜色来源仍是 web/public/_ds/.../tokens/colors.css，换的是**值**不是位置。
  v4 交接包那 12 个变量名（--bg / --panel / --panel2 / --sub / --line / --accent /
  --ok / --bad / --warn / --unk / --shadow）是**设计稿的记法**，NEVER 引进本仓。
  组件侧改动为 0——它们本来就只读 token，这一条是可以数出来的：
  换板前后 var(--<token>) 的出现次数逐个 token 相等，web/ 下除 colors.css 零字节改动。
  否决的另一条路是「v4 变量进 app/globals.css 当唯一层」：那要退役 _ds token 层、
  重映射约 80 个组件、重写 5 个判据文件，且会撞正在跑的第 14 批。

二 · 信息架构：保 29 条路由与 7 个导航入口，只做局部吸收。
  v4 是「3 顶导航 + 判定台 5 tab」的另一套架构，不是现有路由的皮。本版 NEVER 收成三屏、
  NEVER 新建 /judge 一类的合并屏、NEVER 改 NAV_ITEMS。
  只吸收 v4 比现网多出来的两处：
  · 热点广场的 Combo 栏收进假设输入框与三态提示（还需 N 张卡 / 关联假设必填 / 就绪）；
  · 判定台五件之间加一条**屏内互链带**（主题列表 / Gate① / 作业进度 / 受众选择 / vibe_pack）——
    它是屏内的一条导航条，不是路由。

三 · 执行方式：本轮由 steward 出卡，NEVER 直接改码。
  理由是第 14 批在途且碰同一批文件。本批开跑以 docs/FLINT-V041-B14-DONE 落盘为闸。
```

  **影响面**：`PAL-01`（16 个 token 映射进 `web/public/_ds/.../tokens/colors.css`）· `PAL-02`（判据跟着裁决重新瞄准）· `PAL-03`（真栈重拍 `.ui-probe/`）· `PLZ-COMBO-01`（广场 Combo 栏三态提示）· `JUDGE-TAB-01`（判定台屏内互链带）· `AUD-PACK-01`（受众选择与 vibe_pack 两屏补说明文案）· 交接包 `前端设计/应用前端设计需求/design-handoff/`。
  **第一条的可验形式是一个数**：换板前后 `var(--<token>)` 在 `web/app` `web/components` `web/lib` 等处的**出现次数逐个 token 相等**，且 `web/` 下除 `tokens/colors.css` 之外零字节改动。「组件侧零改动」因此不是一句自述——它数得出来。**换的是**值**不是位置**，这句话是本条与被否决那条路的分界：`globals.css` 那条路要退役 `_ds` token 层、重映射约 80 个组件、重写 5 个判据文件（那也是它被**否决**的理由）。
  **第二条要点名两样东西才拦得住**：不许出现的（合并屏、改 `NAV_ITEMS`）与要出现的（**互链带**）。只写「保路由」的话，下一个人新建一个 `/judge` 也自认为没删路由——**加一屏同样是改架构**：29 条路由里那 22 条不在 v4 三屏里的，从此没有人点得到。
  **第三条是一条时序纪律，不是能力划分**：`steward` 出卡而不直接改码，为的是第 14 批在途且碰同一批文件（`web/app/globals.css` · `web/components/shell/AppShell.tsx` · `web/components/workbench/`）——两批并跑会互相覆盖，且第 14 批的五条门会被本批改动污染。闸是 `docs/FLINT-V041-B14-DONE` 落盘（已于 2026-08-12 落）。
  **v4 那 12 个变量名 NEVER 进本仓**（`--bg` / `--panel` / `--panel2` / `--sub` / `--line` / `--accent` / `--ok` / `--bad` / `--warn` / `--unk` / `--shadow`）：搬名字的代价是两套命名并存（`--bg` 与 `--paper`、`--panel` 与 `--surface`、`--accent` 与 `--sulfur`），而**组件读的是哪一套在屏上看不出来**——两套值一旦分叉，屏上只会显得「有几处颜色不太对」。只搬值，名字仍是本仓那一套。

- **DEC-061**（owner 2026-10-27 裁决 · 成文端点的分析来源走甲：服务端换算）：**以下文字是 Claude 在会话里拟的选项文本，owner 从四个选项里点选了这一项**——**NEVER 写成「owner 原文」或「owner 粘贴的」**（同 `DEC-060` 的处置）。

```
DEC-061（2026-10-27，owner 点选 · 选项文本由 Claude 拟）

问：主链第③段（成文）：POST /projects/{id}/report 要的 analysis_id 从哪来？
    （单子 ANALYSIS-ID-HAS-NO-PATH，四选一）
选：甲 · 服务端换算——端点改收发起分析时回的 job_id（字段名 analysis_job_id），
    服务端调既有的 analysis_product_id()（flint/jobs/gate1.py:111）换算。
    零新表，换算规则仍然只在一处，前端不拼 id。
未选：乙 · 新建 analyses 表 / 丙 · 端点改收 job_id / 先不做。
```

  **影响面**：`flint/api/compose.py#ReportSubmit` · `flint/jobs/worker_main.py` 读来源那一段 · `harness/e2e_smoke.py` 与 `tests/m3/test_m3_057.py` 传 `analysis_id` 的调用点 · 工作台中栏 `WB-03-b`（解阻）。
  **「前端不拼 id」是本条的一半**：`"analysis-" + job_id` 这条规则只活在 `analysis_product_id()` 一处；前端只传它本来就有的 `job_id`。

- **DEC-062**（owner 2026-10-27 裁决 · Gate① 第二个真实网络窗口）：**选项文本由 Claude 拟，owner 点选**（同上处置）。

```
DEC-062（2026-10-27，owner 点选 · 选项文本由 Claude 拟）

问：主链第②段（发起分析）要打真实的 github/arxiv。DEC-057 那次窗口已经在
    GATE1-REAL 用掉了（progress-v041.jsonl:533）。要不要再开一次？
选：照 DEC-057 再开一次——只放 github 和 arxiv，总共不超过 40 个请求，
    模型走本机 Ollama（零 key、零付费），每次往返都落到 fixtures/_probe/gate1/，
    跑完转成回放夹具，只授权这一次。目标是从屏上新建的 combo 一路点到判定。
未选：不开，只做离线。
```

  **边界逐条沿用 `DEC-057` 原文**（域名族封闭 github.com / api.github.com / arxiv.org / export.arxiv.org · 额度 ≤40 跨源合并计 · 跑不通就停下开单、NEVER 加码重试 · 留痕格式同 `DEC-052` · 模型只走免费本地档、NEVER 读 API key · 跑完转回放夹具、判据全部离线 · 只授权这一次、每日定时的持续真实分析 NEVER 顺手接上）。
  **与 `DEC-057` 的差别只有出口**：那次的出口是「`cluster_verdicts` 多出一行」；本次是「**从屏上新建的 combo** 一路点到判定」——起点必须是屏上点出来的那个项目，NEVER 拿库里既有的簇冒充。
  **worker 用完即停**（它的 gate1 注的是真实依赖）。

- **DEC-063**（owner 2026-10-27 裁决 · 「提交了→产物是哪一份」：总览改查表＋重写补事件）：**选项文本由 Claude 拟，owner 点选**（同上处置）。

```
DEC-063（2026-10-27，owner 点选 · 选项文本由 Claude 拟）

问：「提交了→产物是哪一份」这两张单怎么修？
    （PROJECT-DOES-NOT-LIST-ITS-OWN-DELIVERABLES ＋ REGENERATE-JOB-WRITES-NO-EVENTS）
选：改查表＋补事件——项目总览不再读 projects.deliverable_ids 那一列，改为直接查
    deliverables 表，并回 version/supersedes，让真相只有一处；重写作业照 run_compose
    的做法推 state=done、写终态事件。
未选：建项回写＋端点回 id。
```

  **影响面**：`flint/api/project_overview.py` · `flint/jobs/*#run_regenerate_job` · 项目总览屏。
  **`projects.deliverable_ids` 那一列保留、不再读**：删列是数据删除，属事前必审，本条不授权。列上写明它不再是真相。
  `blocks.revision` 那一格（重写产物 22 块全是 1）**不在本条范围**，单子里的那句话原样保留待议。

- **DEC-064**（owner 2026-10-27 裁决 · 冻结件修订窗口：缺口提示写成内容＋两版互链字段）：**选项文本由 Claude 拟，owner 点选**（同上处置）。

```
DEC-064（2026-10-27，owner 点选 · 选项文本由 Claude 拟）

问：gap_notice 的 hints_ref 是空串（右栏每次 8 条 404），两版互链没有字段可放，
    这两件都卡在冻结件上。怎么处理？
选：开一次修订窗口一起做——GapNoticeContent 加上 missing_what/why 的内容（提示本身
    就是内容，不用再查一次 id）；Deliverable 加可选字段 sibling_deliverable_id，
    组稿收尾时两边互写。两处都只加可选字段，过 check_frozen_additive。
未选：不动冻结件 / 两件都挪到 V1 之后。
```

  **落地口径的一处更正（Claude 拟选项时没核到，已在会话里当场告知 owner）**：选项里「过 `check_frozen_additive`」读起来像只改 v04 副本；而产品代码用的 `Deliverable` / `GapNoticeContent` 来自 `flint/domain/models.py`，它与 `contracts/models.py` **逐字节相同**（`tests/m1/test_m1_001.py:30` 钉着），不读 `contracts_v04`。所以本窗口的实际改动面是**三个文件同步加同样的可选字段**：`contracts/models.py` · `flint/domain/models.py` · `contracts_v04/models_v04.py`（后者保证 base ⊆ v04，`check_frozen_additive` 仍 exit 0）。
  **窗口边界**：只加带默认值的字段——`GapNoticeContent.missing_what` / `GapNoticeContent.why` / `Deliverable.sibling_deliverable_id`，三个，NEVER 顺手加别的；既有字段与标注一个字不改、不删。
  **改前哈希留档**（2026-10-27 亲验）：`contracts/models.py` `B760C2EEB4E96A96` · `contracts_v04/models_v04.py` `00ED425D85A8C927`。改后哈希在落地卡收卡时补进 trace，并作为新的越界检查对照值。

- **DEC-065**（owner 2026-11-14 裁决 · UI 从 0 重新设计）：**代码块里是 owner 在会话里的两句原话，一字未改**。两句之外的全部设计内容（配色、字体、外壳形态、各屏排版）是 Claude 定的，owner 没有逐项点选——**NEVER 写成「owner 选定了这套配色 / 这个外壳」**。

```
DEC-065（2026-11-14，owner · 会话原话两句）

重构整个UI，现在的UI难用而且丑

这重构的幅度也太小了，我说的是重构，那就是从0重新设计
```

  **取代了什么**：`DEC-060` 第一条（v4 调色板的**取值**）——整板换成 v5；`NAV-ANIME-01` / `NAV-ANIME-02`（浮动药丸条与吉祥物，owner 2026-08-10「要，做全」）——外壳换成左侧固定导航，吉祥物与跟随发光块退役；`TITLE-01`（屏头标题随视口放大到 48px）与 `WIDTH-01`（内容区铺到 1760px）的具体数。
  **没有取代的**：`DEC-060` 第二条「保路由」——24 屏、7 个入口不增不减；「颜色只有一个来源」「组件里不写死颜色」「那一个告警色只留给三处」这几条纪律照旧，新板一样守着；冻结件与 `data-*` 断言面没有动。
  **影响面**：`web/app/redesign.css`（新增，压在 `globals.css` 之上的整层）· `web/app/layout.tsx`（多一行 import）· `_ds/tokens/colors.css` / `typography.css` / `spacing.css`（新取值）· 钉着 v4 取值的判据标为已被取代（`tests/v041/test_palette_v4.py` 8 条、`test_tail_01.py` 3 条），暗纸色相那条换回冷族。落地卡 `REDESIGN-01`，逐项对照与自己定的那些设计决定在 `docs/trace/REDESIGN-01.md`。
  **撤回**：去掉 `layout.tsx` 那一行 import，并把 `_ds/tokens/` 三份文件退回上一个提交。
