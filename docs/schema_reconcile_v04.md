# schema_reconcile_v04 · 冻结件对账结论（SCHEMA-00 产出）

> 输入：`contracts/models.py` + `contracts/protocols.py`（v0.3.3 冻结件，只读）、
> `WORKORDER-v04.md#4`、`docs/schema_reconcile_prefill_v04.md`（owner 交付的预填表）。
> 校验器：`tools/check_frozen_additive.py`。**本文件是对账结论，预填表是输入。**

## 0 指纹核对（预填表基于 owner 上传副本，仓库工作副本为最终权威）

| 文件 | 实测 | 预填表所载 | 一致 |
|---|---|---|---|
| `contracts/models.py` | 30,783 B · md5 `380d7b5a7daee17111a8961f0e3a41c6` | 30783 B · md5 `380d7b5a…` | ✅ |
| `contracts/protocols.py` | 11,099 B · md5 `eb19b73e176e1eb12861c078d9af4c34` | （预填表未载） | — |

行数一处**表述差**：预填表写 1030 行，本地按 `split("\n")` 数为 1031——
差在文件末尾换行符的计数惯例，**同一个文件**（md5 相同）。不是不符。

另核：`contracts/models.py` 与 `flint/domain/models.py` **逐字节一致**（sha256 相同），
既有镜像不变量成立。

## 1 §4 落点逐一对账（acceptance ②）

对账方式：**导入 `contracts_v04/models_v04.py` 后逐项断言字段/类型真实存在**，
不是读文档核对文档。

| I 项 | 落点 | 结果 |
|---|---|---|
| I1 四枚举 | 新增 `Region`/`SystemLanguage`/`AuthorityTier`/`FetchLegalStatus` | ✅ |
| I2 溯源四字段 | **`Doc`**（预填表把清单的 `Origin` 修正为 `Doc`） | ✅ 四字段在 |
| I3 源注册表 | 新增 `SourceEntry`/`SourceRegistry` | ✅ |
| I4 名称三元组 | **`Cluster`**（清单原写 `TopicSeed`，真件无名称字段） | ✅ 三字段在且 `canonical_name` 保留 |
| I5 译文槽 | 新增 `TranslatedText` | ✅ |
| I6 引文原文/派生 | `WhyNowEvidence.event_display` + `Citation.quote_span_display` | ✅ 且 **date display 槽不存在**（槽位收敛） |
| I7 产物语言 | `Deliverable.lang` + `Block.lang` | ✅ |
| I8 图谱三实体 | 新增 `WorkbenchGraph`/`GraphNode`/`GraphEdge` + `GraphSourceKind` | ✅ |
| I9 收藏 | 新增 `Favorite` | ✅ |
| I10 模板注册 | 新增 `TemplateRecord`（与既有 `TemplateSpec` 并存，命名不冲突） | ✅ 两者都在 |
| I11 分享 | 新增 `ShareLink` + `ShareTarget` | ✅ |
| I13 分析上下文 | `AnalysisContext.lang` + `.region`，`locale` 保留 | ✅ 三者都在 |
| J9 币种 | `PricingRecord.currency`/`.region` **既存**，不加字段 | ✅ |
| 事件与作业 | `JobKind` 增三值；`JobEventPayload` 增七成员 | ✅ 10 值 / 11 成员 |

**对账结论：14 项全部相符 → 无需 `CONFLICTS-v04.md`。**
预填表已把清单的三处落点错（I2/I4/事件）与一处槽位收敛（I6）修正在前，
本卡按修正后的落点实现，未再出现新的不符。

## 2 只加不删的机器证据（acceptance ①）

```
models.py    → models_v04.py    : 保留 87 类 / 443 字段 / 1 函数签名 / 31 别名
                                  新增 16 类、13 字段、10 枚举/联合成员
protocols.py → protocols_v04.py : 保留 24 类 / 1 字段 / 40 函数签名
                                  新增 0 类、0 字段、0 成员（本轮零签名改动，仅 docstring 增补）
```

`protocols_v04` 按预填表注记 25 **只增 docstring**：`CitationAligner`（B10 原文-only）、
`JobRunner`（三种新 JobKind 注册进既有 runner）、`JobEventStream`（七个新 payload 复用同一通道）、
`Revalidator`（收藏 stale 走统一口径）。

## 3 冻结件零改动（acceptance ③）

卡上写的是「git diff 为空断言」，但**本仓库不是 git 仓库**（无 `.git`），该命令无从执行。
改用**等价强度**的证据——md5 指纹与卡开工时逐字节一致：

```
contracts/models.py    md5 380d7b5a7daee17111a8961f0e3a41c6  == 开工时指纹
contracts/protocols.py md5 eb19b73e176e1eb12861c078d9af4c34  == 开工时指纹
```

指纹比 `git diff` 更强：它连「改了又改回去」的中间态都不放过，且不依赖版本控制。

## 4 v04 副本的构造方式

`models_v04.py` 由脚本从冻结件生成：11 处**精确锚点**插入，每处命中次数不等于 1 即中止，
**NEVER 手抄冻结件**（手抄是「只加不删」最容易失守的地方）。新增块一律带
`# —— v0.4 纯新增 ——` 注释，落点依据写在注释里。

头部按 v0.3.3 口径重写（补上「∨ owner 变更」）——预填表注记 1 指出冻结件头部文字滞后，
副本按 v0.3.3 正确口径书写，**原件不动**。

## 5 dataclass 默认值顺序（构造期真跑过）

`Deliverable` 与 `Block` 末尾已有带默认值的字段，故新增的 `lang` **必须带默认**
（`= "zh"`），否则 Python 在类创建时直接 `TypeError`。
`Cluster` / `Doc` / `AnalysisContext` / `WhyNowEvidence` / `Citation` 无默认值字段，
新增字段按原风格不带默认。

这不是纸面推理——`models_v04.py` **真的被 import 执行过**（`Doc` 13 字段 / `Cluster` 13 字段 /
`JobKind` 10 值），dataclass 装饰器全部成功求值。
