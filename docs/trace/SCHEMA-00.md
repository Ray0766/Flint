# SCHEMA-00 trace — 冻结件对账 + contracts_v04 基建 + additive 校验器 @2026-08-02

V1 首卡。依赖的 9 张 V0 卡全部 verified。

## 1 装载清单（§2.3）

| 装了什么 | 字符 |
|---|---|
| SCHEMA-00 卡 | ~1,100 |
| `docs/schema_reconcile_prefill_v04.md`（owner 预填表，全文） | ~5,700 |
| `contracts/models.py` 的**目标类片段**（8 处 sed 切片，非整本） | ~2,400 |
| `contracts/protocols.py` 的类清单 + 4 处 docstring 片段 | ~1,200 |
| `WORKORDER-v04.md#4` 的 I 项标题行 | ~600 |
| **合计** | **~11,000**（≈11k tokens，占预算 27.5%） |

`contracts/models.py` 全文 30,783 B **NEVER 整本装载**——符号表用 AST 脚本取，
类体用行号切片取。

## 2 test-first

1. 先写 `tools/check_frozen_additive.py`；
2. 跑 verify_cmd → **红**（`文件不存在：contracts_v04\models_v04.py`）；
3. 另跑「冻结件 vs 它自己」→ **绿**（探测器的地板：自比必须过，否则后面全是假红）；
4. 生成两份副本 → verify_cmd **exit 0**。

## 3 我自己的校验器里有一处空转，被变异体抓出来了

写完 5 个变异体做反证时，**s5（删掉 `CitationAligner.align` 的 `stage` 参数）没有报错**。

查因：`Surface` 用 `ast.get_source_segment(text, node.args)` 取签名，
而 **`arguments` 结点没有 `lineno`/`col_offset`**，该函数对它一律返回 `None` →
`_src` 退化成 `""` → 所有签名都在拿 `"" == ""` 比。
**protocols.py 的 40 个方法签名，那条断言一直是空转的。**

修法：改用 `ast.unparse`（对任何结点都给规范化源码，顺带抹平换行与引号风格差异——
那些本就不算「改动」）。修后 s5 立刻报 `签名被改：CitationAligner.align`。

顺带发现同一函数还有第二处漏改（模块级函数分支 `_src(node.args, text)` 未跟着改签名），
虽然本轮两个文件都没走到那条分支，仍一并修掉——留着就是下一个文件的坑。

**教训写进了函数 docstring**，防止后人再用 `get_source_segment` 取签名。

## 4 self_review（self_review=true）

### ① 测试真实覆盖 acceptance

| acceptance | 证据 | 反证 |
|---|---|---|
| 全部符号与字段在 v04 副本原样存在（AST 级，只加不删） | verify 输出：models 保留 87 类/443 字段/31 别名；protocols 保留 24 类/40 签名 | **s1** 删字段 → `字段被删：Keyword.aliases`；**s2** 改标注 → `字段标注被改：Cluster.canonical_name`；**s3** 改类名 → `类被删：Citation`；**s4** 删枚举成员 → `JobKind 丢了成员`；**s5** 改签名 → `签名被改：CitationAligner.align` |
| §4 落点逐一对账；不符 → CONFLICTS-v04.md | **导入 v04 模块后逐项断言 14 项**（不是文档核文档），全部相符 → 无需 CONFLICTS | 断言里含反向条件：I6 断言 date display 槽**不存在**（槽位收敛）、I10 断言 `TemplateRecord` 与 `TemplateSpec` **两者都在** |
| 原 contracts/ 零改动 | md5 双文件与开工时一致；且与 `flint/domain/models.py` 逐字节一致 | 见 §5 |

五个变异体退出码实测 **1/1/1/1/1**，落盘副本 **0**，冻结件自比 **0**。

### ② 无冻结件偏离

`contracts/` 只读——本卡全部产出写在**新目录** `contracts_v04/`。
副本相对冻结件的差异只有三类：新增类、新增字段、别名新增成员——由 verify_cmd 逐符号断言。

### ③ 无禁用词

见收卡命令输出（四件产出均无命中）。

### ④ 复用断言在位

本卡不碰运行期通道，H 组无实现级命中；但 `protocols_v04` 的四处 docstring 增补**就是把
H1/H4/H7 的复用纪律写进契约**：新 JobKind 注册进既有 runner（H7）、七个新 payload 复用同一 SSE 通道（H4）、
收藏 stale 接 `Revalidator` 薄适配器（H1）。

### ⑤ 装载未超预算

~11,000 字符 ≈ 11k tokens，占 **27.5%**。

## 5 acceptance ③ 的执行偏离（如实记）

卡上写「git diff 为空断言」，**本仓库不是 git 仓库**（无 `.git`），该命令无从执行。
改用 md5 指纹与开工时逐字节比对——**证据强度不低于 git diff**（连「改了又改回去」都抓得到，
且不依赖版本控制）。已写进 `docs/schema_reconcile_v04.md#3`。

## 6 DECISIONS

- **DEC-004**：`pyproject.toml` 的 ruff per-file-ignores 增 `"contracts_v04/*" = ["I"]`。
  来由：v04 副本**逐字继承**冻结件的 import 排版；给它排序就等于让副本与冻结件产生差异，
  而「与冻结件逐字对齐」正是 additive 校验器要守的东西。与既有的 `"contracts/*" = ["I"]` 同理同源。

## 7 产出

| 文件 | 说明 |
|---|---|
| `contracts_v04/models_v04.py` | 冻结件 + 16 新类 / 13 新字段 / 10 新枚举·联合成员；**脚本按 11 处精确锚点生成，NEVER 手抄** |
| `contracts_v04/protocols_v04.py` | 冻结件 + 4 处 docstring 增补，**零签名改动** |
| `tools/check_frozen_additive.py` | AST 级 additive 校验器（V1 全阶段的闸） |
| `docs/schema_reconcile_v04.md` | 对账结论：指纹核对 / 14 项落点 / 只加不删证据 / 零改动证据 |
| `pyproject.toml` | 1 行 ruff 豁免（DEC-004） |

**未动**：`contracts/`（md5 双验证）、`flint/`、`tasks.json`、`CLAUDE.md`。
