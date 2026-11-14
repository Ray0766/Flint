# trace · 核心生成引擎 + 块级指令式重生成里程碑（FE-CORE-*）

## owner 裁决（@2026-07-30）
Q-008=选1（建生产生成引擎 + regenerate 执行器）；Q-007=块级；授权最小冻结件修订
（regenerate 加 guidance + block 寻址）。范围 A~E（冻结件 / 生产生成器+prompt / 块级重生成 /
Job→worker 接线 / guidance 穿透+前端指令框+i18n）。硬线：LLM 一律录制回放测（M1-008），
真机 qwen3.6 录制/端到端 = 资源消耗，STOP 报 owner 授权后再跑。

## 后端现状（Q-008 查明，本里程碑要补的）
- 生成走 `_default_generator`（离线确定性桩，无 LLM/prompt）；无生产章节生成器。
- regenerate Job 无派发消费者（PgJobRunner.submit 仅落库+arq 钩子）；PgRegenerateService
  （M3-042 章节级）仅测试调用；run_compose 忽略 regenerate 载荷。
- 铁律护栏已在：`draft_section` 校验生成块 fact_ids 必在账本内，账本外事实 → DraftViolation
  拒稿——用户指令 NEVER 能编造出处（结构性保证，无需新造）。

## FE-CORE-001 · 冻结件最小修订（DONE，review 待）
**唯一冻结件改动 = 给 `InterventionService.regenerate_section` 加两个可选参数**（owner 授权）。
逐字 diff（contracts/protocols.py 与 flint/domain/protocols.py **同改**，保 M1-001 保真）：

```diff
-    def regenerate_section(self, deliverable_id: str, section_id: str) -> str: ...
+    def regenerate_section(self, deliverable_id: str, section_id: str, guidance: str | None = None, block_id: str | None = None) -> str: ...
     # → job_id; 只动未受保护 block (locked ∨ author=="user" ∨ user_modified 原样
     # 保留); 产出新 GenerationRecord, Deliverable 版本+1。
+    # guidance: 用户自然语言指令, 只引导生成方向, NEVER 当事实写入 (账本外事实经通道门拒稿);
+    # block_id: 非 None → 块级 (仅重生成该块, 保护同节未选中兄弟块不动); None → 章节级。
```

- **最小性**：只这一个方法多两个**可选**参数（默认 None，向后兼容，既有 section-level 调用不破）
  + 两行镜像注释；lock/inject_evidence/dispute 冻结签名**逐字不变**（test 断言）。
- **保真**：两文件同改（line 207 一行、注释 +2 行），仅 import 行差异（M1-001 规则）保留。
- **扩参 vs 新方法**：取**扩参**（最小改动——一个方法多两参 < 新增整方法）。block_id=None →
  章节级（现有语义）；非 None → 块级（FE-CORE-004 实现）。
- 验收：tests/m1/test_regenerate_contract_v2.py（2 测试：新参在场+可选、其余签名不变）+
  tests/m1/test_m1_001.py（保真 7 测试）全绿；mypy --strict flint 198 文件净。
- **NEVER 新增类型/超「加两参」**——未触发 STOP。

## 里程碑拆卡（S5，≤2 cycles/卡，已并入 tasks.json）
7 张子卡（milestone FE-CORE），tasks 208→**215**、total_cycles 227→**238**、critical_path
**53 不变**、review_gates +7、acyclic/orphans/errors 净；archive_write 备份 tasks.json.bak-3（H-3）。
test_m4_023 len 215、exit_ids FE-004→**FE-CORE-007**（前端总出口终端）。

| 卡 | 范围 | cycles | depends_on |
|---|---|---|---|
| FE-CORE-001 ✓DONE | 冻结件最小修订（regenerate +guidance+block_id） | 1 | M3-048 |
| FE-CORE-002 | 生产章节起草 prompt 实体 + prompts.lock | 1 | M3-023 |
| FE-CORE-003 | 生产 LLM BlockGenerator（qwen3.6，替桩，过通道门） | 2 | FE-CORE-002 |
| FE-CORE-004 | 块级重生成（只目标块、保护未选中兄弟块、S2-5、版本+1） | 2 | 001, 003 |
| FE-CORE-005 | Job→worker 接线（regenerate 端到端真跑） | 2 | 004 |
| FE-CORE-006 | guidance 穿透 + 铁律断言（指令 NEVER 变事实） | 1 | 003, 004 |
| FE-CORE-007 | 前端块级指令框（复用 L1，S2-5 门）+ 最小 i18n 地基 | 2 | 005, 006, FE-004 |

## 执行状态 + 资源消耗 STOP（owner 授权前置）
- **FE-CORE-001（冻结件）已建成 + 全绿**（本轮）。FE-CORE-002~007 为后续增量。
- **硬线遵守**：FE-CORE-003/005 的 LLM 生成一律**录制回放/合成 fixture** 建逻辑与测试
  （M1-008，CI 零联网零付费 S2-7）。**真机 qwen3.6 录制跑 / 端到端验证 = 资源消耗触点**——
  按 owner 令 STOP 报授权后再跑，NEVER 擅自跑。故 003/005 落码时先以合成 fixture 建逻辑+测试，
  真机录制单列，等待 owner 授权。

## FE-CORE-002 · 章节起草 prompt 实体（DONE，走(a)离线）
prompts/section_draft@1.md（版本化，走既有 M2-004 版本库规格）+ prompts.lock.json 登记
（section_draft@1 → hash bb26174a8fd8，update_lock 重算全锁）。prompt 含铁律约束：只引用
usable_facts 的 fact_id、账本外不引用不编造、三通道、gap 留白、user_guidance 只引导不当事实。
test tests/fe_core/test_section_prompt.py 3 绿（按锁加载 + 铁律 token 在场 + verify_lock 净）。

## FE-CORE-003 · 生产 LLM BlockGenerator（DONE，走(a)离线 fixture）
flint/compose/llm_generator.py：BLOCK_SCHEMA（heading/paragraph/gap_notice）+ build_prompt
（section_spec + usable_facts + guidance）+ _parse_blocks（LLM JSON → Block，author=system）
+ llm_generator_factory（插 ComposeDeps.generator_factory，provider/prompt/guidance 注入闭包）。
产出过 draft_section_with_channels 门。**_default_generator 桩保留**（NEVER 删，离线确定性测试用）。
- **离线 fixture 贴合真实**：LocalProvider 走 httpx.MockTransport（M1-008），块 paragraph 内容
  取自 assets/prod_caliber/qwen3.6_27b.json 的真实 qwen3.6 摘要正文。CI 零联网零付费（S2-7）。
- test tests/fe_core/test_prod_generator.py 5 绿：真实 prose→gate 过 / 账本外 fact→DraftViolation
  拒稿（铁律护栏）/ gap_notice 留白 / 桩仍在 / schema 形。mypy 净。
- **真机 qwen3.6-under-section_draft 录制/端到端 = 资源消耗触点**：本轮以合成 fixture 建逻辑+测试，
  真机录制验证「qwen3.6 在 section_draft@1 下产出的块质量」待 owner 授权后再跑（FE-CORE-005 端到端一并）。

## FE-CORE-002+003 review（生成引擎增量）
fresh audit a2146017：7/8 CONFIRMED，1 阻断 = S2-8 禁用词 as etc（llm_generator.py:29 注释）→
按 S9 修单行注释（除词）+ 重跑关闭（ruff 净 + fe_core 8 绿），**review_passed**。
铁律确认：产出经**真** draft_section_with_channels 门（账本外 fact→DraftViolation，非 mock）；
全离线（MockTransport）；真实 qwen3.6 prose 复用；桩保留；冻结件未触；无真机运行。
**非阻断观察（登记 v0.4-问题单）**：paragraph 正文逐字过，validate_channels 只查 profile 裸值、
不查正文裸数字（冻结 M3 fact-channel 设计固有——事实按 id/FactCell 引用）；prompt 指令缓解，
非本增量回归。

## FE-CORE-004 · 块级重生成架构（DONE，走(a)离线）
flint/intervene/block_regen.py：regenerate_block（纯函数）——block_id 目标块只重生成，
其余块原样携带；BlockProtected（保护块拒）/ TargetNotInSection。产出经**真**
draft_section_with_channels 门（NEVER 绕）。硬断言 test-first（tests/fe_core/test_block_regen.py 4 绿）：
① 只目标块变、未选中兄弟块（含未保护 b1）字节不变；② 保护块 b3(locked)/b4(user_modified)
字节不变、对保护块下重生成→BlockProtected 拒（S2-5，复用 guard_rewrite）；③ 账本外 fact→
DraftViolation（经真门）。离线 fixture 重生成内容取自真实 qwen3.6（qwen3.6_27b.json opportunity 节）。
- **版本 +1 换绑属持久化**：PgRegenerateService 现有 section-level version+1，FE-CORE-005 接线
  块级路径时施加；本卡为纯块级逻辑（结构不变量）。
- **未动冻结件**（除已授权 guidance/block_id）：块级逻辑用现成 Block/guard_rewrite/通道门，
  无需再扩契约——未触发 STOP。

## FE-CORE-008 · 正文裸数字 needs_review 软扫描（DONE，owner 裁 B）
flint/compose/naked_numbers.py：UNIT_NUMBER_RE（$ 前缀金额 / \d%百分比 / \d(万|亿)）+
scan_block_naked_numbers（只扫段落 TextSpan(kind=text)）+ mark_naked_numbers（functional：
命中→replace(needs_review=True, review_severity="advisory") + 报告 block_id→token；NEVER
就地改输入）。**软标非硬拒**：NEVER 进 validate_channels hard violations、NEVER DraftViolation；
走现成 Block.needs_review（L0 已渲染），不新造机制；结构化 fact/price 单元不经手（走硬门）。
review_reason 保持 None（冻结 ReviewReason 三枚举无裸数字项，NEVER 误用）。
test tests/fe_core/test_naked_numbers.py 5 绿：无出处 40%/500万/$3000/12.5亿→置位；日期/序号/
个/节/项/v2→不误标；table FactCell 不经手；functional 不改输入；干净正文不标。
了结 v0.4-问题单「正文裸数字」观察（状态更新为软标了结）。

## FE-CORE-005/006/007（走(a)离线，DONE）
### FE-CORE-005 · Job→worker 接线（flint/jobs/regenerate_worker.py，5 测试）
parse_regenerate_payload（载荷→RegenerateRequest 含 block_id/guidance）+ rebind_and_reindex
（换绑 new_deliverable_id + 逐节 order 重排，与 M3-042 版本复制同形）+ regenerate_section_blocks
（章节级：未保护块整节重生成经真门、保护块携带 guard_rewrite）+ dispatch_regenerate（按 block_id
路由块级(FE-CORE-004)/章节级 → 产新全树）。块级/章节级产出均过 draft_section_with_channels 真门
（账本外 fact→DraftViolation）。合成生成器注入（离线）。版本+1 落库属 PgRegenerateService 同事务。
### FE-CORE-006 · guidance 穿透 + 铁律（llm_generator.build_block_regenerator，4 测试）
build_block_regenerator：只重生成目标块、guidance 穿进 prompt「只引导方向、NEVER 当事实」。
铁律断言：guidance 要证据外数字 → 若模型硬引账本外 fact 则通道门 DraftViolation 拒（NEVER 编造
出处）；正路模型改 gap_notice 留白过门。无 guidance→prompt 无 user_guidance 块。RecordingProvider
离线捕获 prompt（无网无模型）。
### FE-CORE-007 · 前端块级指令框 + i18n 地基（web，4 测试；+ 后端 body→payload 接线）
web/lib/i18n.ts（最小 i18n 地基，key→zh-CN + t()，④留缝，新串走 key）；
interventionClient 加 "instruct_regenerate" 动作（并进干预动作集、受同一 S2-5 门）+
regenerateBlockWithGuidance（带 block_id+guidance 调端点→job_id）；
InstructionRegenerateBox 组件：**S2-5 保护块无框（渲染 null）**，非保护块指令框+提交→
块级 guided-regenerate→复用 L1 openJobStream 流式状态，文案全走 i18n key。web 43 测试绿。
后端接线（flint/api/interventions.py regenerate 端点）：读可选 body {block_id, guidance} →
Job payload（action=regenerate_block + block_id + guidance），缺 body（L2 章节级）向后兼容。
tests/m3/test_m3_048.py +1（enqueue 捕获断言 payload 含 block_id+guidance）；bodyless 旧测仍绿。
**离线链路已通**：前端指令框 → 端点 → Job payload → worker parse(005) → dispatch → 块级重生成(004)
+ guidance(006)，全过真通道门。**唯一剩余 = arq 消费者实调 dispatch + 真机 qwen3.6 端到端录制/
验证（单一授权点）→ STOP 报 owner。**

## FE-CORE-005 端到端真机跑（owner 单一授权 @2026-07-30，qwen3.6 免费档，DONE）
**授权**：owner @2026-07-30 授权一次真机 qwen3.6（本机 localhost:11434，免费档非付费）e2e。
**worker 消费者**：flint/jobs/regenerate_job.py run_regenerate_job——载 DB(当前树+deliverable+
账本) → 建生产生成器(LocalProvider qwen3.6:27b, disable_reasoning=True) → dispatch_regenerate
按 block_id 派发块级 → 过真 draft_section_with_channels 门 → 落库(新 deliverable 版本+1、
supersedes 旧版、新 GenerationRecord、新 block 树)。
**跑法**：种子 deliverable(summary 节 4 块：标题/目标啰嗦块 b-sum-2/锁定保护块 b-sum-3/
未选中未保护兄弟 b-sum-4) + 账本(1 frozen fact「数据标注市场年增速约三成」) → payload
{action:regenerate_block, block_id:b-sum-2, guidance:"更简洁、突出真实技术优势、去空话、只用有据事实"}。
**结果（1 次调用，cost 0.0 FREE，真实 qwen3.6）**：
- 版本 +1（→2）；目标块 b-sum-2 已变；**未选中兄弟 b-sum-4 字节不变**（块级关键承诺 held）；
  保护块 b-sum-3 字节不变（S2-5）；标题 b-sum-1 不变。
- 旧 b-sum-2：「本项目是一个平台，用了很多先进的技术…总之是个很好的项目。」（空话）
  → 新 b-sum-2：「数据标注市场年增速约三成」，**fact_ids=['fact-mkt-1']**（引了账本内那条 fact）。
**如实评估（免费档 best-effort，NEVER 粉饰）**：链路端到端通、块级承诺 + 铁律双双 held——
qwen3.6 只引账本内 fact、零编造，按 guidance 去了空话。但产出**偏瘦**：坍缩成只复述唯一
可用 fact。此系**正确的接地行为**（池里仅 1 fact + guidance「只用有据事实」→ 拒绝注水），
非管线缺陷；更丰满的重生成需账本里有更多 fact。管线以接地压过了流畅度——符合三铁律设计。
**录制回放**：真实产出录 assets/prod_caliber/fe_core_regen_qwen36.json（M1-008）；
tests/fe_core/test_regen_job_e2e.py 回放该产出跑全链（本地 PG），CI 离线断言端到端 5 项。
**授权用尽**：仅此一次真机跑；后续回归全走此录制回放，NEVER 再擅自跑真模型。
