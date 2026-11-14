# 试跑缺陷回填环（M4-037 · @2026-07-28）

> 环规格：试跑（M4-033~036）发现的包/生成器/校验器缺陷 → 回填修正 →
> 三包重产 → 全门重跑 → 闭环记录。每条 finding 携：发现点 / 病灶侧 /
> 回填动作 / 回归证据 / 状态。

## F-1 · 包完整性评测 single-source 检查过采集

- **发现点**：M4-033 试跑样本一首跑——真实全包（九章）过
  eval/pack_integrity 时 single-source 面误报「表与 payload 漂移」。
- **病灶侧**：**校验器侧**（评测启发式），包本身正确——S6 context
  refs 表与 S7 verify_cmd 表本就各携任务行（各章各自投影），全文扫描
  把三张表的行都采进了对照集。
- **回填动作**：eval/pack_integrity.py single-source 检查截取 S5 章
  区间（章头至下一章头），对照对象回到「S5 表 vs tasks.json」的本义。
- **回归证据**：M4-031 回归 4/4 绿（简单包不受影响）；三包重产后
  integrity 全绿（下节合跑）。
- **状态**：**closed**（M4-033 trace 双记）。

## F-2 · 执行器视角缺陷可检出性反证（非缺陷，能力面确认）

- **发现点**：M4-036 harness 篡改反证用例——ghost ref 与非 pytest
  verify_cmd 均被对应面逐卡指认（rate<1 联动）。
- **结论**：包缺陷若出现会被执行器模拟面捕获——回填环的**下游安全网
  在位**；本条为能力确认记录，非待修项。
- **状态**：recorded。

## 回填后重产重跑（本卡验收第二行，tests/m4/test_m4_037.py 机器执行）

1. `fixtures/_generate_trial_specs.py` 三包全量重产（门拒即 raise，
   产出即三与门绿）；
2. 三包 × eval/pack_integrity 四面全绿；
3. 三包 × harness/spec_trial 逐卡三面全绿，一次通过率 1.0
   （report_only，Z 待 owner）。

## F-3 · prod_caliber `_guidance_for` 子串误匹配（owner 裁决 2-2 @2026-07-28 入账）

- **发现点**：owner 第三轮复核——`_GUIDANCE_RULES` 关键词 `"ask"` 以子串
  匹配命中 `"t**ask**_dag"`，致 vibe_pack `S5_task_dag` 节收到「本节数字
  MUST 全部用 PriceCell 标注」的**预算类指引**（张冠李戴），该节 v3
  作答率 0/4。
- **病灶侧**：harness 组稿脚手架（子串匹配无词边界）；连带背景实测
  （owner 复核采信）：指引覆盖节 48/68=71% vs 未覆盖节 35/104=34%，
  差 2.1 倍断崖——0.44 测的是「提示词有没有碰巧提到考题」而非模型
  能力。
- **回填动作**：**由 2-1 结构性改动消除**——`_GUIDANCE_RULES` 整表删除，
  组稿输入改为注入本节 check_questions 原文（SectionSpec 设计即随节
  携带；关键词匹配路径整体不复存在），不单独修补。
- **回归证据**：2-1 落地测试断言无 guidance 残留 + 注入为原文；
  阶段二整体 review_gate（2-4）复核。
- **状态**：closed-by-design（结构性消除）。

## 环终态

- open findings：0；closed：2（F-1、F-3）；能力确认：1（F-2）。
- 后续新 finding 入本文件追加（append-only），回填-重产-重跑同规格。
