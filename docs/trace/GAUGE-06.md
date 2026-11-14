# GAUGE-06 · F-04 接口断言真化 + F-03/F-06 两处措辞与真件对齐

**卡** `docs/steward/tasks-v041-b2.json#GAUGE-06` · **批次** v0.4.1 第 2 批 · **开工** 2026-08-03T22:41Z

## 1. 装载清单（inputs 来源）

| 装载物 | 来源 | 用途 |
|---|---|---|
| 卡面 GAUGE-06 | `tasks-v041-b2.json` | acceptance / outputs / verify_cmd |
| `docs/review/终检-v04.md#F-04` 全节 + F-06 段 + B 组取证纪律段 | context_refs | 判词与三档取证纪律 |
| `flint/design/prod_render.py` 全文（两个渲染器 + 查找逻辑） | inputs | 被测真件 |
| `flint/analysis/deep_job.py` docstring 段（1~25 行） | inputs | 待改措辞 |
| `docs/异见清单-v04.md:19`（A4 行）+ `:72`（终检判词行） | inputs | 待改措辞 ×2 |
| `tests/v04/design/test_prod_render_gate.py:155~185` | 追加 | 那条 `hasattr` 断言的落点 |
| `contracts/models.py:707` + `contracts_v04/models_v04.py:801-804` | 追加 | JobKind additive 的**真件证据** |

装载约 15k tokens。

## 2. acceptance①：二选一选了 ②「入参形状互斥」——理由三条

卡上给两条路：① 抽一个 `DesignRenderer` Protocol 两边实现；② 口径改成「两路径入参形状互斥」
并按形状断言。**选 ②**：

1. **① 做不出诚实的 Protocol**。两个 `render` 的参数表**没有交集**
   （`html` vs `template_id + slot_values`）。要让它们实现同一个 Protocol，只能把签名放宽成
   `render(*args: Any)` 之类——**那是 `hasattr` 换了身衣服**，正是本卡要消灭的东西；
   否则就得改其中一个的签名，而那要动一个已封版模块的公开面。
2. **共同接口会削弱这道门**。这条 acceptance 的产品意义是「生产路径不收 html」（终检原话）。
   抽一个共同 Protocol 等于给两条路径造一个**共同调用点**——调用方从此可以拿着一个
   `DesignRenderer` 变量在两条路径之间切换，而「生产渲染器没有接受 html 的口子」
   这件事就不再是类型层面的事实，退化成一句注释。
3. **真件本来就是这么写的**。`ProductionRenderer` 的 docstring 原话是「只接受 `template_id`
   + 插槽值。**没有接受 html 的口子**」。措辞要对齐的是它——NEVER 反过来改真件去迁就
   一句写错的 acceptance。

**这条选择本身是一次口径收窄**（与 GAUGE-03 的「服务端→单进程」同型）：卡面写的
「两路径共用 Renderer 接口」在 v0.4 里从来不成立，本卡把它改成真的那件事，并留下痕迹。

## 3. `hasattr` 那条断言的下场（改既有文件之一）

**改前**（`tests/v04/design/test_prod_render_gate.py:158`）
```python
def test_both_renderers_share_one_interface() -> None:
    ...
    assert hasattr(prod, "render") and hasattr(explore, "render")
    assert type(prod) is not type(explore)
```
**改后**：改名为 `test_the_two_renderers_are_two_implementations_not_one_interface`，
`hasattr` 那行删掉，换成「无共同基类、互不是对方实例」的真断言，docstring 写明这条测试
原来叫什么、为什么改，并指向本卡的完整判据。

**为什么非改不可**：acceptance① 原话「**NEVER 让 `hasattr` 继续冒充**」。只在新文件里写
一条真断言是不够的——旧那条还在的话，下一个读它的人仍然会以为「共用接口」被验过了；
而那个测试名本身就是那句假话。`test_the_old_hasattr_claim_is_gone_from_the_v04_gate` 守着它不回潮。

## 4. probe_bites 当场拒了我的第一版探针（本卡最值得记的一段）

反例探针用 GAUGE-03 建的 `tests/_meta/probe_bites.py` 咬。第一版把
`ProductionRenderer` 换成一个收 html 的类，被守的两条断言按 `_render_params(cls)` 读**类属性**。
跑出来：

```
AssertionError: 抽掉 flint.design.prod_render.ProductionRenderer（给生产渲染器开一个收 html 的口子）之后：
测试确实红了，但替换件**一次都没被调用**。被测代码没走到那条路，这次的红与被抽掉的机制无关，结论作废
```

**这正是那道检查存在的理由，而它拦下的是我自己**：被守的断言只是读了类上的 `render` 属性，
替换件从头到尾没被实例化过——「红」与「换掉的东西」之间的因果没有被证明。

改法不是放宽检查，是**让断言问真对象**：`_production_render_params()` 现在真造一个
`ProductionRenderer(registry=object(), owner=object())`，问它的 `render` 收什么。
既满足那道检查，断言也更贴近真相——客户拿到的是这个对象，不是那个类。
（构造不做校验：它是 dataclass，模板查找发生在 `render` 里，本条只问签名。）

**登记一条真限制**（§8）：`probe_bites` 的第四道检查用「被调用次数」当证据，对**只被读取
而不被调用**的替换件（类、常量、Protocol）会误判。本卡绕过去了，但那是个真洞。

### 另一次变异考：真给生产渲染器开一个 html 口子

不满足于探针，按终检的三档取证纪律又走了一次 ③（真改源文件 → 跑 → 从备份还原）：

```
改 flint/design/prod_render.py: render(self, template_id, slot_values, html: str = "")
→ 3 failed, 7 passed   （形状断言红、探针也红——「替换前就是红的」）
还原 → 10 passed
prod_render.py sha256 前缀 b05d84fb8d3ba60b，与终检 DESIGN-31 revert 法记录的 b05d84fb…4684 一致
```

## 5. F-03/F-06 两处措辞（改既有文件之二、之三）

### 5.1 先证伪那句话本身

```python
frozen = set(get_args(contracts.models.JobKind))
v04    = set(get_args(contracts_v04.models_v04.JobKind))
v04 - frozen == {"translate", "design_generate", "template_solidify"}   # 真件里就有
```
`contracts_v04/models_v04.py:801-804` 在**同一个增量里**就 additive 加过三个 JobKind 值，
走 `contracts_v04/` additive 通道 + `check_frozen_additive.py`——**S2-1 一次都没被越过**。
所以「造一个新的 JobKind 要改冻结件（S2-1 NEVER）」站不住。
这条断言是下面两处措辞改动的**前提**：前提不验，改措辞就成了另一种「因为有人这么说」。

### 5.2 `flint/analysis/deep_job.py` 的 docstring

**改前**（`:6`）：「造一个新的 JobKind 要改冻结件（S2-1 NEVER），而自建一套提交路径会带来
第二份幂等键与重试语义」——前半句与真件不符。
**改后**：明写「**都不是**『新增 JobKind 会动冻结件』——那句话与真件不符」并给出 additive
的证据，然后列两条真理由：① 深度是**档位**不是另一种作业；② 自建提交路径带来**第二份
幂等键与重试语义**。
**为什么非改不可**：acceptance② 点名这一处；且它是**代码里的**一份错误理由，读代码的人
会照着它做判断（F-06 的更正原话：这句话「不在异见清单里独有，代码 docstring 里也有一份」）。

### 5.3 `docs/异见清单-v04.md` 两行

- `:19` A4 行的「理由」列：换成上面两条真理由，并在 `〔…〕` 里注明原写什么、为什么不符。
- `:72` 终检判词行末尾追加 `〔v0.4.1 GAUGE-06 两处均已改，tests/v041/test_renderer_interface.py 守着不回潮〕`。
**为什么非改不可**：`:72` 写着「措辞待改 2 处」，改完不销账的话这份文档自己就带着一条过期的待办。
**NEVER 删掉原判词**——那是病史，删了下一个人只会看到「本来就是对的」。

### 5.4 一处判据设计：留痕与判据不该互相取消

第一版断言 `"新增 JobKind 要动冻结件" not in row` 当场红了——**因为改动说明里逐字引了被改掉的
旧说法**。同型的问题也出现在 §3（新 docstring 引用了旧的 `hasattr` 断言原文）。
两处都不是放宽断言，而是把判据挪到该在的层：
- A4 行：先 `re.sub(r"〔[^〕]*〕", "", row)` 摘掉改动说明再判正文——否则等于要求留痕
  「不许提到自己改了什么」；
- 旧测试文件：判**代码层**（AST 里没有 `hasattr` 调用、没有旧测试名的 `FunctionDef`），
  而不是判原文——否则等于逼后人把病史从注释里抹掉。

## 6. acceptance③：`deep_job.py` 只动 docstring 的证明

**指纹在改动前采集**（先采后改，顺序不可倒）：

```
剥掉全部 docstring 后的 AST → sha256 = 4836466c3854743d5b091fb25c36837cb1c3a9d0e0b3fff7c5f389219ee838ff
改 docstring 后复算            → 4836466c…38ff   一致
函数/类清单不变：ChargeLandingMissing / DeepAnalysisPricing / ChargeIntent /
                 DeepAnalysisSubmission / _RunnerLike / deep_analysis_payload /
                 submit_deep_analysis / __init__ / submit
mypy --strict flint → Success: no issues found in 273 source files
```

**用 AST 而不是文件哈希**：文件哈希会被 docstring 改动本身带偏，证明不了「只改了 docstring」。
配一条指纹自证 `test_the_fingerprint_would_notice_a_code_change`：往剥完的 AST 里塞一行
`MARKER = 1`，指纹必须变——否则「指纹没变」可能只是因为这把尺子对什么都不敏感。

## 7. verify 与 self_review

```
verify_cmd: pytest tests/v041/test_renderer_interface.py -q        → 10 passed
连带跑改过的旧文件: tests/v04/design/test_prod_render_gate.py       → 合计 22 passed
ruff check . --no-cache → All checks passed!
mypy --strict flint     → 273 files, no issues
```

**① 测试 ↔ acceptance 映射**

| acceptance | 测试 | 判据 |
|---|---|---|
| ① `hasattr` 换真断言（选 ② 并说明） | `test_the_two_render_signatures_have_no_parameter_in_common`、`test_production_render_has_no_hole_that_takes_html`、`test_neither_renderer_is_pinned_to_a_shared_base`、`test_the_old_hasattr_claim_is_gone_from_the_v04_gate` | 形状互斥（交集为空）+ 旧断言在代码层消失；理由见 §2 与模块 docstring |
| （① 的强度） | `test_these_assertions_really_bite_when_production_grows_an_html_hole` | probe_bites 咬：替换前绿、替换后红、替换件真被用到 |
| ② 两处措辞与真件对齐 | `test_the_three_v04_job_kinds_really_went_through_the_additive_channel`（前提）、`test_the_module_docstring_no_longer_blames_the_frozen_contract`、`test_the_dissent_row_carries_the_two_real_reasons` | 先证伪旧理由，再断新措辞在位、旧措辞不在正文里 |
| ③ 只动 docstring | `test_deep_job_changed_only_its_docstring` + `test_the_fingerprint_would_notice_a_code_change` | AST 指纹（改前采集）+ 指纹自证 |

**② 无冻结件偏离**：`contracts/`、`contracts_v04/`、`flint/domain/` 一字未动（本卡只**读**它们做证据）。
`flint/analysis/deep_job.py` 只动 docstring（AST 指纹为证），`flint/design/prod_render.py` 一字未动
（变异实验已还原，sha 复原）。

**③ 禁用词**：三个改动/新增文件扫描，六词 0 命中、收尾「等」0 命中。

**④ 复用断言**：`tests/_meta/probe_bites.py`（GAUGE-03 产物）真调用，不是 import 了不用——
它当场拒了本卡第一版探针（§4），这就是复用有效的证据。

**⑤ 装载预算**：约 15k tokens。

## 8. 顺序纪律（§4.2）与登记未做

**顺序**：本卡先改真件（deep_job docstring / 异见清单 / 旧测试）再写新测试，**又是反的**。
连续第三张。但本卡有一处顺序是对且关键的：**AST 指纹先采后改**——采晚了就什么都证明不了。

**登记未做**：
1. **`probe_bites` 第四道检查的盲区**：用「被调用次数」当「替换件被用到」的证据，
   对只被**读取**的替换件（类、常量、Protocol）会误判成「结论作废」。本卡绕过去了
   （让断言问实例），但那是真洞——建议下批立卡改成「被调用或被读取」，
   同时要改 GAUGE-03 那条构造反例的匹配串。本卡 NEVER 顺手改它：改判据要连带改它自己的验收。
2. **DESIGN-31 卡面 acceptance② 的文字没改**：`tasks-v04.json` 是 v0.4 封版的机读真相，
   改它属 owner 面（与 GAUGE-05 §9-1 同一条边界）。本卡只让「真相是什么」在代码与测试里可查。
3. **契约里那个 `Renderer` Protocol（`contracts/protocols.py`）与这两个渲染器的关系未处理**：
   它的签名是 `render(deliverable_id, fmt)`，与两者都不是一回事——三者并存是否需要改名以免
   将来有人按名字认亲，属冻结件面，NEVER 自行动。
