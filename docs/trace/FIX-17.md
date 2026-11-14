# FIX-17 · 两条来源的说法并排，屏上看不出谁说的

**结论**：owner 选甲。署名上屏了，单据关了。**而首版差一点又造出同一个病**（见 §4）。

装载：卡 `FIX-17` · `docs/blocked/SOURCE-COLUMNS-DOES-NOT-SHOW-WHO-SAID-IT.md`
· `web/components/source-columns/SourceColumns.tsx`

---

## 1 改前：这个组件说的正是它自己

`SourceColumns` 的全部理由写在它自己的文件头：

> 读者失去了「谁说的」这个唯一能判断可信度的东西。

而它把来源只放进 `data-source-id`——**DOM 里有，屏上一个字都没有**。

地区那一列不够顶：列标题是地区，只在两个源恰好分属两个区时才顺带区分了它们。
库里的实况是 `global = 103 · CN = 89 · NULL = 1`，绝大多数簇的源同区或无区。

## 2 为什么此前没有判据抓到

`HOTSPOT-07` 的 10 条判据用 `within(column).getByTestId(...)` 逐列查 `data-source-id`。
**那条判据是对的、也留着**——它防的是混列。

它量不到的是另一件事：「在 DOM 里」与「在屏上」。
读屏软件念不出一个属性，肉眼也看不见它。`data-*` 是给取证用的，产品语言是给人看的。

## 3 改前 / 改后 / 为什么非改不可

| 文件 | 动作 |
|---|---|
| `web/components/source-columns/SourceColumns.tsx` | 多渲染两格：署名 + 分隔符（v0.4 封版件，`DEC-021` 要求停下报 owner，**owner 已在单上裁决选甲**） |
| `web/components/source-columns/sourceName.ts` | 新增：四个源 → 词条 key 的**明写**映射 |
| `web/messages/{zh,en}.json` | 各加 4 个 key |
| `web/app/globals.css` | 署名与分隔符的两条样式 |

**key 逐个写死**，不拼前缀：拼出来的 key grep 不到，`i18n_key_defined` 会把它报成未定义，
而那份报告是对的——没人能从源码里看出这个前缀底下要有哪几个 key。
（第 7 批的 `JobDeniedNotice` 栽在同一处。）

**认不出来的 id 原样显示**：NEVER 编一个名字，也 NEVER 说成「未知来源」——
前者假装我们认识它，后者把「我们没给这个源起过名」说成「这条陈述来路不明」。

「四个源」的真相取自 `flint/sources/*.py` 的 `source_id`，**前端不抄一份清单**：
新增一个源而前端没跟上，判据当场红。

## 4 断点：改完看了一眼屏，发现首版又造出了同一个病

首版两个 `<span>` 直接相邻，屏上出来的是：

```
Google 趋势脑机接口
```

**读者分不出名字在哪儿断开。** 也就是说：署名上屏了，而「分得出谁说的」这件事
仍然没做到——**只是从「看不见」变成了「看得见但读不开」**。

改后：冒号是**独立的一格**（样式失效时也分得开），且 `aria-hidden`，
NEVER 混进原文那一格——原文要逐字（B9）。署名用 `--text-meta` 加粗，
不上强调色：它是元信息，那句原话才是内容，用色彩强调署名会把注意力从原话上抢走。

屏上（`.ui-probe/fix17-two-sources.png`，本卡看过）：`Google 趋势： 脑机接口`。

**这一处是「改完自己看一眼再收卡」抓到的，源码层与 vitest 都判不出来**
（两个 span 各自的 `textContent` 都对）。所以补了一条判据：
整行的 `textContent` 必须逐字等于 `名字：原话`。

## 5 另外两个小断点

**① 说明文字里写出了要避免的那个拼法。** `sourceName.ts` 的注释里原本写着
「不是 `t("source.name." + id)`」——扫描器读到的是字符，它分不出「示范」与「在用」，
于是把 `source.name.` 报成未定义的 key。**报告是对的。** 改法照旧：换个说法，不放宽尺子。

**② 判据自己也踩了同一脚。** `test_an_unknown_source_id_is_shown_verbatim` 拿整份文件查
「未知来源」，而注释里正写着「NEVER 显示成未知来源」。改成只查代码行。

同一形状，本批第十五、十六次。

## 6 门

```
pytest tests/v041/test_source_columns_attribution.py -q   10 passed
vitest run components/source-columns                      16 passed（既有 10 条一条没动）
vitest run                                                85 files · 857 passed
pytest tests/v041/ -q                                     2901 passed
tsc --noEmit                                              0
ruff check .                                              All checks passed
```

CSS 那条被 `test_the_plaza_styles_use_tokens_except_the_named_geometry` 拦了一次：
`margin-inline-end: 0.25em` 是写死的间距，改成 `var(--sp-1)`。**尺子是对的。**

单据 `SOURCE-COLUMNS-DOES-NOT-SHOW-WHO-SAID-IT.md` 已关，关闭理由写在头部，原文一字未改。
