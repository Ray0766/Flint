# MIGRATE-01 trace — 接地增强(a) 规格 v04 @2026-08-02

## 1 装载清单（§2.3）

| 装了什么 | 字符 |
|---|---|
| MIGRATE-01 卡 | ~500 |
| `WORKORDER-v04.md#2-J3` | ~700 |
| `PRINCIPLES#B9` / `#B10` 两条（已在 docs/PRINCIPLES-v04.md） | ~700 |
| `contracts/` 真签名：WhyNowEvidence / Citation / Alignment / CitationAligner | ~600 |
| **合计** | **~2,500**（≈2.5k tokens，预算 40k，占 6.3%） |

只取签名、NEVER 整包装载 `contracts/models.py`（30,783 字符）。

## 2 test-first

先写 `tools/check_grounding_spec.py` → 跑 → **红**（`规格文档不存在`，exit 1）→ 再写规格 → **exit 0**。

## 3 中途自纠：一条打不到的分支＝死代码

校验器初版用固定名单 `("WhyNowEvidence","Citation","CitationAligner","Alignment")` 去查
「文档引用的冻结件符号是否存在」。写完就发现**这条分支永远打不到**——名单里全是已存在的名字，
无论文档怎么改都不会红。那是自我安慰式的断言。

改成：扫 §0 那个**自称「冻结件里的相关真件」**的代码块，块内每个类型名都去 `contracts/` 核实，
并显式排除 v04 新类型（`GroundingOnTranslationError` / `GroundingResult` / `TranslatedText`——
本轮才引入，冻结件里理应没有）。现在这条分支能被打到，见 §4 的变异体 g4。

## 4 self_review（§4.6，self_review=true）

### ① 测试真实覆盖 acceptance

| acceptance | 校验点 | 反证（变异体 → 实际报错） |
|---|---|---|
| 三条增补：校验输入=原文字段 | `### A1` 存在且正文含「原文」+ `PRINCIPLES#B10` | **g5**（抽掉 A1 的 B10 依据）→ `增补条 A1（校验输入）正文缺关键内容：PRINCIPLES#B10` |
| 三条增补：译文禁入比对 | `### A2` 存在且正文含 `NEVER` + `PRINCIPLES#B10` | **g1**（整条删掉 A2）→ `缺增补条 A2（译文禁入比对）` |
| 三条增补：译文引用可展开原文 | `### A3` 存在且正文含「展开」+ `PRINCIPLES#B9` | 同机制（A3 与 A1/A2 走同一断言路径） |
| 含 event 文本/日期一致性判据的伪码 | `## B` 下必须有 ``` 围栏，且块内含 `event`、`event_date` | **g2**（把 `event_date` 改名）→ `伪码缺判据要素：event_date` |
| 错误类型 `GroundingOnTranslationError` | `## C` 定义它，且必须写「何时抛」 | **g3**（把「何时抛」改成「触发」）→ `错误类型小节缺「何时抛」——只给类名不给触发条件等于没规定` |
| （规格挂在真件上） | §0 引用的类型逐个到 `contracts/` 核实 | **g4**（往冻结件块里塞 `TranslationLedger`）→ `规格自称引自冻结件、但 contracts/ 里没有这些类型：['TranslationLedger']` |

五个变异体全部被抓，每条 acceptance 都有一个「破坏后变红」的证据，无空转。

### ② 无冻结件偏离

`contracts/` **只读未动**——校验器只 `read_text` 不写。规格引用的
`WhyNowEvidence` / `Citation` / `CitationAligner` / `Alignment` / `Doc` 五个符号
经校验器逐个到 `contracts/` 核实存在（verify 输出里逐个列出）。
`contracts_v04/` 尚未存在（SCHEMA-00 才建），additive 校验器同理，**无输出可贴，如实记**。

### ③ 无禁用词

`Select-String "适当|合理|必要时|大约|尽量|若干"` → `docs/grounding_spec_v04.md`、
`tools/check_grounding_spec.py` 均无命中。

### ④ 复用断言在位

H1~H8 无命中。但规格正文本身写死了两条复用纪律，属同一精神：
(a) 判据挂既有 `CitationAligner` 两段通道，**NEVER 新开第二条对齐管线**；
不过的 evidence 走既有 `needs_review` → blocking 路径，**NEVER 新造拦截机制**（规格 §D 表）。

### ⑤ 装载未超预算

~2,500 字符 ≈ 2.5k tokens，预算 40k，占 **6.3%**。

## 5 规格里两处我明确定死、值得 owner 知道的判断

1. **来源没有可提取日期 → 判不过**（NEVER 以「没写就算过」放行）。「来源没写日期」与
   「日期对得上」是两回事，把前者当后者放行正是这个洞的成因。
2. **(a) 的结果只有过/不过两态**，NEVER 与 `Alignment` 的四态混用——后者是 `CitationAligner`
   的产物，两套语义混用会让「部分对齐」被当成「接地通过」。

## 6 产出

| 文件 | 说明 |
|---|---|
| `docs/grounding_spec_v04.md` | 规格：§0 洞 → §A 三条增补 → §B 伪码双判据 → §C 错误类型 → §D 与既有件关系 |
| `tools/check_grounding_spec.py` | 校验器，ruff `--no-cache` 净 |
