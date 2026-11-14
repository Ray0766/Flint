# PRIN-01 trace — 七条前置原则落盘 + 一致性校验器 @2026-08-02

v0.4 增量第一张卡（`depends_on: []`，也是 dag_report 关键路径的头）。

## 1 会话启动序列（worker.md §2）

| 步 | 结果 |
|---|---|
| 2.1 读 `docs/progress-v04.jsonl` 末 20 行 | **文件不存在 = 全新开局**。按规则从 tasks-v04.json 依赖就绪的第一张卡起 |
| 2.1' 选卡 | 103 张卡里 `depends_on` 为空的**只有 PRIN-01** 一张，无歧义 |
| 2.2 读对应 trace | 不存在（新卡） |
| 2.3 装载 | 见下表 |
| 2.4 | 未依赖上一会话记忆；progress-v04 里没有任何 verified 行 |

### 实际装载清单（§2.3 要求逐次记）

| 装了什么 | 字符 |
|---|---|
| `prompts/worker.md` 全文 | 3,623 |
| `WORKORDER-v04.md#3`（108–169 行） | 3,776 |
| `WORKORDER-v04.md#6` H 组复用清单（486–500 行） | 1,474 |
| `eval/ledger_append.py`（查能否复用，见 §3） | 1,451 |
| `CLAUDE.md#S2+S3` | ~1,800 |
| PRIN-01 卡 + V0 九卡表 + dag_report 摘要 | ~2,600 |
| **合计** | **14,724** |

按「中文 1 字符 = 1 token」的**最坏**口径估 ≈ 14.7k tokens，预算 40k，占 **36.8%**，未超。
**没装**：`tasks-v04.json` 全文（73,593 字符）、`WORKORDER-v04.md` 全文（38,403 字符）——
卡内容与 §3/§6 都是脚本切片取的。

`context_refs` 里的 `contracts_v04/` **不存在**（由 V1 的 SCHEMA-00 建）。本卡是文档卡，
不产生类型与签名，未装载、也无从装载——不是遗漏。

## 2 test-first（§4.2）

verify_cmd 就是校验器本身，所以「先写失败测试」= **先写校验器、先跑红**：

1. 写 `tools/check_principles_doc.py`；
2. 跑 `python tools/check_principles_doc.py docs/PRINCIPLES-v04.md` → **exit 1**：
   `落盘文档不存在：docs\PRINCIPLES-v04.md`（红态确认，有输出为证）；
3. 再落盘 `docs/PRINCIPLES-v04.md` → 同一条命令 **exit 0**。

**落盘文档是用校验器自己的 `extract_section` 从工单生成的，NEVER 手抄**——
「与工单逐字一致」这条要求，手抄恰恰是它失守的地方。生成一次之后，
哈希比对的作用是**探测漂移**（谁改了任何一边就红），不是自证。

## 3 复用检查（先查后写）

台账追加**复用** `eval/ledger_append.append_entry`（通用 path+dict，不绑事件词表），
NEVER 手拼 JSON。H1~H8 复用清单逐条比对：**本卡一项都不命中**——
H 组八项全是运行期/功能件（Revalidator、JWT 中间件、导出管线、SSE、undo 栈、
by_source 分列、JobRunner、combo 假设通道），本卡是文档 + 一个独立校验脚本，
不碰其中任何一条通道。

## 4 self_review（§4.6，本卡 self_review=true）

### ① 测试真实覆盖 acceptance（映射 + 反证）

| acceptance | 校验器里的实现 | 反证：破坏后确实会红 |
|---|---|---|
| 七条各含 规则/反例/校验点/违反时 四段，逐条断言四段齐全 | `check_parts()` 对每条逐段查 `- **X**：` 前缀，并断言冒号后**非空** | 变异体 m1（删掉 B5 的「校验点」行）→ `PRINCIPLES#B5：缺「校验点」段`，exit 1；m4（把 B9 的「反例」正文清空）→ `PRINCIPLES#B9：「反例」段是空的`，exit 1 |
| 七条 | `len(blocks) != 7` 断言 + 编号序列与工单一致 | 变异体 m2（整条删掉 B8）→ `应有 7 条原则，实际 6 条：A3, B4, B5, B7, B9, B10`，exit 1 |
| 与工单 §3 正文逐字一致（哈希比对） | 两侧同一归一后 sha256 比对，不等时再打印**首个差异行号 + 两侧原文** | 变异体 m3（`{zh, en}` 改一个字符成 `{zz, en}`）→ 哈希不等 + 定位到第 7 行，exit 1 |

四个变异体退出码实测 **1 / 1 / 1 / 1**，落盘件 **0**。
即：这四条断言都不是空转——每一条都有一个「本来会绿、破坏后变红」的证据。

### ② 无冻结件偏离

本卡**不触碰**任何契约：`contracts/` 只读未动，`contracts_v04/` 尚未存在（SCHEMA-00 才建），
本卡产出是一份 Markdown 与一个独立脚本，无类型、无签名。
additive 校验器 `tools/check_frozen_additive.py` 属 SCHEMA-00 的产出，**此刻不存在，
故无输出可贴**——如实记，不假装跑过。

### ③ 无禁用词

`Select-String -Pattern "适当|合理|必要时|大约|尽量|若干"`：
- `tools/check_principles_doc.py` → 无
- `DECISIONS-v04.md` → 无
- `docs/PRINCIPLES-v04.md` → 无（且工单 §3 原文本身也无，照抄不引入）

### ④ 复用断言在位

H 组无命中（见 §3），故无 H 组 import 断言可写。台账复用记录在 §3。

### ⑤ 装载未超预算

14,724 字符 ≈ 14.7k tokens（最坏口径），预算 40k，**36.8%**。

## 5 DECISIONS

- **DEC-001**：「工单 §3 正文」边界 = `## §3 ` 标题行 → 下一个 `## ` 前，去掉末尾 `---` 与首尾空行；
  落盘文档即这一整节（含标题行）。哈希前两侧同一归一（CRLF/CR → LF、去尾部空白）。
  理由：不归一的话，Windows 编辑器写出的 CRLF 会让两份**完全相同**的内容假红。

## 6 产出文件清单（§4.7）

| 文件 | 说明 |
|---|---|
| `docs/PRINCIPLES-v04.md` | 七条原则，3,266 字符，由工单 §3 抽取生成，sha256 `e025e9fee04b3613…` |
| `tools/check_principles_doc.py` | 校验器，ruff `--no-cache` 全绿 |
| `DECISIONS-v04.md` | **新建**，DEC-001 |
| `docs/progress-v04.jsonl` | **新建**，started + verified 两行 |

## 7 本卡之外发现、我没动的事

1. **owner 交付的 `tools/validate_dag_v04.py` 过不了 `ruff check .`**：`UP009`（多余的 UTF-8
   编码声明）+ `I001`（import 未排序），两处都是 `[*]` 可自动修。它是 owner 交付件、不在本卡
   outputs 里，我**没有动**。但 worker.md §5 的全局门含 `ruff check .`，**V0 出口 SELFCHECK
   会被它绊住**——届时按 DEC 处理或请 owner 定夺。
2. **worker.md §5 的全局门写的是 `mypy --strict src`，本仓库没有 `src/`**（Python 包是
   `flint/`，v0.4 新件在 `tools/`）。V0 是文档阶段免 mypy，本卡不受影响；**V1 起会撞上**，
   到时按 §1.4 写问题单，不自行择一。
3. `tools/`（复数）经 PRIN-01 卡 `outputs` 确认就是 v0.4 工具目录（与既有 `tool/` 单数并存，
   后者放 `labeling.py`）——归位时我提的那个疑点，到此**由卡自证，不是笔误**。
