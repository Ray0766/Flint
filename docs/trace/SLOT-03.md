# SLOT-03 · `translate` 作业接上消费者

> v0.4.1 第 6 批第四张。`depends_on: ["SLOT-01"]`（已 verified）。

## 装载清单

`tasks-v041-b6.json#SLOT-03` · 工单 §3 · `flint/jobs/dispatch.py`（context_refs）·
`flint/i18n/{name_display_job,translator}.py` · `flint/jobs/{design_generate,worker_main,gate1}.py`
（消费者与注入的既有形状）· `contracts_v04/models_v04.py#Cluster/TranslatedText` ·
本机 55432 的 `information_schema` 实查。约 14k tokens，**未超 40k**。

## 一、开工前查到的两件事（决定了这卡怎么做）

工单说「`translate` 作业至今没有消费者 → 接消费者」。接之前先看这个消费者
**从哪读、往哪写**，两处都不成立：

1. **读哪一段原文没成文。** 冻结件 `contracts_v04#Cluster` 在 `canonical_name`
   那一行留着话：「`canonical_name` 保留：与 `name_native` 的关系由
   **REGION-04 命名规则成文**」——也就是说这两者今天什么关系**还没写下来**；
2. **写到哪里没有落点。** 全库实查：`name_native` / `name_display`
   在 `information_schema.columns` 里**零命中**。`name_display` 今天只活在
   `flint/i18n/name_display_job.py` 与它自己的测试里。

**两件都不是本卡能替产品决定的**，而且都不在卡上 outputs（一个要成文、一个要迁移）。

## 二、所以取源与落盘是**注入**的

消费者只做派生，`load_target` / `save_target` 两个端口由装配处给——
与 `DesignGenerateDeps` 把 provider 注入进来是同一个理由（那份 docstring 的原话：
「运行时用哪个模型是**注入方**的事」）。

**没配就大声缺**：`_translate_handler` 抛 `HandlerDepsMissing`，
消息里逐条点名缺什么、以及那两个未决各自的出处。

猜一段原文去翻是这里最坏的做法：屏上会出现一个**语义正确、指向错误**的译名，
而它与译对了长得一模一样。

## 三、一行派生逻辑都不写

派生转调既有的 `derive_name_display`——它已经守着三条：

| 纪律 | 它怎么守 |
|---|---|
| B7 原文一字不动 | 只写 display 槽；冻结件 `__setattr__` 还会拒绝二次赋值 |
| B8 译名带机翻标记 | `TranslatedText(translated=True, translator=版本, source_field=…)` |
| A7 翻不出来留空 | 降级的那一档**不写入**，UI 退回单行 |

再写一份的后果不是重复劳动，而是**同一个名字在两条路上被译成两个样子**，
而 UI 只显示其中一个，没人知道另一个存在。

## 四、改了两个既有文件，逐处记账

### 1) `flint/jobs/dispatch.py`

**改前**：`UnwiredKindReason` 里有 `translate` 一条，写着「仓里还没有消费者」。
**改后**：那一条删掉，`WIREABLE_KINDS` 里加 `"translate"` 并注明消费者在哪。
**为什么非改不可**：这张表是「哪些 kind 有人取」的唯一真相；接了不改，
worker 取到仍会抛 `JobKindNotWired`——**接线等于没接**。

### 2) `flint/jobs/worker_main.py`

**改前**：`WorkerDeps` 没有 `translate_deps`；`build_handlers` 八条；
docstring 写「七个可接线 kind」（**那个数早就与表对不上了**，本次顺手改成不带数）。
**改后**：加注入位 + `_translate_handler`。
**为什么非改不可**：`build_dispatch_table` 要求 `WIREABLE_KINDS` 每条都有 handler，
少一条它当场拒——所以这两处必须成对改。

**docstring 里那个数为什么改成不带数**：写死一个数，每加一条 kind 就要改一次，
而**忘了改时它是一句假话且没有任何判据会响**。

## 五、动了两条既有判据（都是例子过期，不是接线出错）

1. `tests/v041/test_design_generate_job.py::test_the_other_two_unwired_kinds_stay_declared`
   钉着 `set(UnwiredKindReason) == {"translate", "template_solidify"}`。
   **改的是判据**：那份名单是「现在还缺谁」的真相，它跟着事实走；
   钉死一个过期的集合，只会让下一次真正的接线被判成错。改名并写明改因；
2. `tests/v041/test_asm_03.py::test_unwired_kind_still_fails_loudly_through_the_worker_table`
   写死拿 `translate` 当「没接线」的例子。**改成从 `UnwiredKindReason` 里取**
   （`min()`）——下一次接线它会自动换到剩下那条上；名单空了 `min()` 会抛，
   那时就该删掉这条判据。**这比再写死一个 kind 名好**：同一个坑本仓这是第二次踩。

## 六、判据（18 条）

- **分派表**：进 WIREABLE / 出 Unwired / 覆盖判别联合不倒 /
  **阴性对照**：漏掉 `translate` 时 `IncompleteDispatchTable` 必须响；
- **B7**：原文与 `canonical_name` 都没变，外加**冻结件自己会拒绝改写**那条阴性对照
  ——没有它，「原文没变」可能只是这一轮碰巧没人去改；
- **B8**：每条译名带 `translated=True` + 译者版本 + 源字段；
- **A7**：降级那一档不写入 · 拿原文冒充要红 · **一档都没翻出来时 `name_display` 恒 `None`**
  （留个 `{}` 的话 UI 那边 `display && …` 仍为真，屏上会出现一个**空的次要行**，
  那比单行更坏：它看起来像译文没加载出来）· 降级不打断整批；
- **重跑只补缺的**：既有译文不重问译者、不被覆盖；
- **缺东西大声说**：取不到的目标点名进 `missing`；payload 形状不对（源字段/空目标/空语言）
  逐条拒——「一种语言都不翻」最坏，因为**它会安静地成功**；
- **零真实出网**：AST 断言本模块零 HTTP 客户端 import + 整段跑在
  `respx.mock(assert_all_mocked=True)` 零路由下；
- **报告加得起来**：`translated + degraded + len(missing) == 目标数`——
  对不上就说明有目标**无声消失**了。

## 七、verify

```
pytest tests/v041/test_translate_job.py -q                    → 18 passed
pytest tests/v041/test_asm_0{2,3,4}.py test_design_generate_job.py
       tests/v04/i18n -q                                      → 105 passed
ruff check . --no-cache                                       → All checks passed
mypy --strict flint                                           → 303 files, no issues
python tools/check_line_endings.py                            → 219 个文件全是 LF
python tools/check_outputs_declared.py                        → 只剩白名单历史条目
```

两次返工：`WorkerDeps` 的必填参数（判据里手抄 profile 十一个字段 → 改成照
`test_design_generate_job.py` 的做法从签名生成，冻结件加字段时不会波及本卡）；
`test_asm_03` 那条例子过期（见第五节）。

## 八、self_review

① 判据覆盖 acceptance 五条，且**四条是阴性对照**（漏 kind 要红 / 冻结件拒改写 /
拿原文冒充要红 / 空语言表要拒）；
② 零冻结件改动——本卡反而**靠**冻结件的 `__setattr__` 当判据；
③ 无禁用词；
④ 改动面：新增 `flint/jobs/translate.py` + 测试，改 `flint/jobs/` 两处
（全在 outputs），另改两条既有判据的**例子**（第五节逐条记因）。
`flint/api/` 卡上列了但本卡没动——装配注入面等落点定了再接，见第九节；
⑤ 装载 ≈14k tokens。

## 九、留给下游（**本卡没做完的那一半，逐条列名**）

1. **落盘面未定**：`name_display` 全库没有列。要真跑起来得先定它落哪
   （`clusters` 加列 / 单开一张表 / 走 `snapshots`），那是一次迁移 + 一次产品决定；
2. **取源未成文**：`canonical_name` ↔ `name_native` 的关系等 REGION-04；
3. **上屏未做**：卡上 outputs 没有 `web/`，本卡不碰前端。
   `HotspotCard` 的次要行槽与 `PLAZA-03` 的 A7 降级判据**原样不动**，
   广场今天照旧只显主行——**那是如实的**：还没有译名可显；
4. **装配注入**（`flint/api/app.py` / `worker_main` 的 deps 实参）等第 1、2 条定了再接。
   在那之前提交一条 `translate` 会拿到 `HandlerDepsMissing` 并被点名缺什么——
   **这比静静排队好**，也比猜一段原文去翻好。
