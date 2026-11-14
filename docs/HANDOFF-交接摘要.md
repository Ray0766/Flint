# 燧石 Flint · AI 执行交接摘要（@2026-07-28，交接给下一个执行 AI）

> **新会话第一动作（S8 硬性规定）**：读 `docs/progress.jsonl` 末 20 行 →
> 定位在跑/被阻任务 → 读对应 `docs/trace/*.md` → 再动手。NEVER 依赖本
> 摘要或任何会话记忆做进度判断——本摘要只是地图，台账才是真相。

## 一、项目与治理（不变量）

- **项目**：V1 商用 MVP——四热点源日更 → 证据卡/工作台 → Gate① 四分类
  → 深度报告 → 计划书（受众分叉：五套人类模板 / vibe_pack AI 执行包）
  → 支付。规范 = 仓根 `CLAUDE.md`（S1~S9）+ `tasks.json`（机读任务
  DAG，203 卡）+ `contracts/`（冻结件，NEVER 改）。
- **执行环**（S7）：领卡 → 台账 started → **先写失败测试** → 实现 →
  verify_cmd 绿 → 全局门（`ruff check . && mypy --strict flint eval
  harness && pytest -q`，Makefile gate 目标）→ trace 合册先行在盘 →
  （review_gate 卡→送审核 agent）→ 台账 verified/review_passed。
- **审核 agent**：SendMessage 至 `a9b45239fb301f208`（五项检查单：
  acceptance 语义覆盖/冻结件零偏离/S2-8 禁用词/台账 trace 完整/装载
  预算）。同因连续 2 次失败 → S9 升级，NEVER 第三次盲试。
- **台账纪律（机械执法，tests/m4/test_ledger_pairing.py 常驻）**：
  ① 成对性——verified/blocked/review 事件必有 started；② ts 纪元锚
  （LEDGER-TS-NOTE 行）之后 MUST 机器钟 UTC（`date -u`）非递减 + 不得
  超前真钟 300s；BACKFILL 行须 note 携 "BACKFILL" **且**带 recorded_ts
  字段。两个冻结豁免闭集（35 卡前判例期 / 单行估写异常）NEVER 增补。
- **S2-8 禁用词**（spec/注释即红）：适当/合理/必要时/等/大约/尽量/若干
  （合成词如幂等豁免）。

## 二、已完成（里程碑视角）

| 里程碑 | 状态 | 出口 |
|---|---|---|
| M1 数据与索引层（41 卡） | ✅ 关闭 | docs 内出口报告 |
| M2 检索与 Gate①（52 卡） | ✅ 关闭 | X=1.0/Y=1.0 离线线，owner 签字 |
| M3 Ledger 与文书（66 卡） | ✅ **有条件关闭** | docs/M3-出口报告.md：check/配比两行为自证口径⚠️，兑现判据挂 M4-044「生产口径验证」节（唯一关门位）；兑现前 NEVER 表述「生产就绪」 |
| M4 spec 导出（44 卡） | **40 verified + 6/6 中程门全过**（023/007/015/029/036/038）；M4-040/041 blocked（见下）；M4-043 verified；M4-044 草案态 | docs/M4-出口报告.md（草案，签字栏空置） |

M4 交付面：spec 导出全链（store→S1~S9 章族→合卷→tasks.json 互证→
contracts 逐字节副本→zip→fmt=pack 端点→spec_export job 断点续跑）、
registry 实调线（PyPI/npm/crates 回放客户端→锁版→[replaced]→批校验→
不可用整包禁导出）、DagValidator 线、三试跑样本+执行器模拟 harness、
五线回归 harness（m4_regress）、生产 provider 地基（Anthropic 记账 +
LocalProvider）。全量测试 **1057 绿**；mypy strict 221 文件零错误。

## 三、生产口径验证长征（M4-040/041，当前主战场）

M3 携带条件 = 接真 LLM 后 N≥12 真实组稿：①逐题语义作答率、②渲染字量
实测配比。owner 裁决走**免费档本地模型**（产品分层级；ollama
localhost:11434，四模型：qwen3:30b / gemma4:31b / gemma4:26b /
qwen3.6:27b，配置经 FLINT_LOCAL_* 环境变量）。

**已发生的实测与教训（全部在案，NEVER 粉饰）**：
- v3 批次（SCALE=1200 缩尺）：qwen3:30b 作答 0.442/配比 0.212、
  gemma4:31b 0.523/0.233——**双线均不达标**，已进出口报告 §二实测表并
  标注历史批次不作产品指标；gemma4:26b 思考超预算截空判失败行；
  trail 在 assets/prod_caliber/。
- owner 复核结论：0.44 测的是「提示词有没有碰巧提到考题」（组稿输入与
  考核面同为 check_questions）——据此三阶段整改：
  - **阶段一（7 项，已关）**：出口报告实测表、SCALE 1200→6000、
    usable_for_gate 三与门位、tokens 节退出配比判定面、ts 断言加固、
    修复环一次性开关（--no-length-repair）、两条事实声明。
  - **阶段二（已关，2-4 过审）**：check_questions **原文**注入组稿
    （_GUIDANCE_RULES 整表删除，F-3 findings 在案）；**owner 投放
    held-out 题库** assets/heldout_questions.yaml（v1.0，129 题，只读！
    sha256[:16]=A80C8C73AF03C8DB）——判分只从题库取题（question_id 落
    trail），装载器四断言（43 对全覆盖/id 唯一/与模板题零交集/组稿路径
    隔离）；**首轮 report_only**（0.90 线 NEVER 沿用，门槛 owner 见数
    再裁）。
  - **阶段三（未启动，等 owner 明确放行）**：两支探针——
    `python -m harness.prod_caliber --model gemma4:31b --samples 1
    --no-length-repair` 与同参开修复环（SCALE=6000、并发 4、
    OLLAMA_NUM_PARALLEL=4 + KEEP_ALIVE=-1 已在服务端生效）；落账
    wall/tokens/调用/逐节字量/界内判定 + 修复触发率与成本倍数后
    **立即停**，等 owner 定全量范围。

**当前铁律（未解除）**：任何以抬作答率为目的的提示词/guidance 改动
全面禁止；题库只读（改题走 S9）；CONCURRENCY=4 与 compose_sample 串行
节循环不动；不跑 qwen3.6:27b、不加第五模型。

## 四、未来要干的重点（按序）

1. **等 owner 放行阶段三** → 跑两支探针 → 两组数字落账 → 停，owner 定
   全量范围（跑几个模型、开不开修复环）。
2. **全量跑批**（owner 定的范围）→ 首轮 report_only 数字 + 四模型对照
   表（assets/prod_caliber/comparison.md，时延维度跨批不可比已声明）→
   owner 据此裁：作答率门槛、免费档默认模型。
3. **关门链**：门槛裁定后按 usable_for_gate/verdict 判定 → 若达标：
   出口报告「生产口径验证」节关门（改报告 + test_m4_044 同批改写）→
   M4-040/041 转 verified → 三卡送审核 agent（040/041/044 都是
   review_gate）→ owner 出口签字（含 Z 线初值记录）→ **M4 关闭**。
4. **M4 关闭后**：前端批次展开（S5 表：广场/工作台/Gate/报告查看器/
   audience 选择器+vibe_pack 查看器/SSE 渐进/支付/tiptap↔Block，
   规模 48，依赖 api 就绪）——判例：每个批次展开跟在里程碑签字之后，
   展开时 MUST 带 cycles/verify_cmd/context_refs/review_gate。
5. **悬而未决的 owner 裁决**（问题单 docs/v0.4-问题单.md 全记录）：
   thesis/grant × 商业题材配对缺陷（三选一）；tokens↔汉字换算口径
   （vibe_pack 配比绝对字量面）；Z 线初值；付费档（Anthropic）启用时
   按档位另跑生产口径验证。
6. **开放硬化项**（非阻断，登记在 v0.4-digest）：gate1 end 事件入步
   事务；生产 LLM plan 重算确定性。owner 修订通道项（冻结件文案）勿动。

## 五、环境速查（Windows 宿主）

- venv：`./.venv/Scripts/python.exe`；Bash 路径
  `cd "/c/Users/Ray/Desktop/Vibe coding/燧石 Flint（热点分析+项目计划书）"`；
  脚本需 `PYTHONPATH=.`；中文控制台会 GBK 乱码 → 结果落 UTF-8 文件再读。
- Docker：`$env:Path += ";C:\Users\Ray\AppData\Local\Programs\DockerDesktop\resources\bin"`；
  pg16@55432 / redis7@56379（compose 已起）；alembic head=0016。
- Ollama：localhost:11434；改服务端 env 须进程内设置后重启
  "ollama app.exe"（用户级 setx 不会被继承）。
- PDF 验证走 Linux 容器（flint-pdf:69，Q-003 判例），Windows 无 GTK。
- 台账写入：PowerShell `Add-Content -Encoding utf8`；读用 utf-8-sig；
  ts 必须 `date -u` 实读，NEVER 估写（有断言，会当场抓红）。
