# DESIGN-31 trace — [隔离·G6] 生产渲染门（只认已注册模板）@2026-08-03

> **隔离带卡 + owner_review**。按 DEC-000 默认照做；开工前复查 `DECISIONS-v04.md`
> 无划除记录，工单 §11-③ 明写「认同，这是两阶段模型的承重墙 …… 明确不推荐（划掉）」。

## 1 为什么本轮先做 31 再做 28（有意偏离卡号序）

SELFCHECK-V4#④ 里我给 owner 写过一条顺序约束：**「DESIGN 组开工时 MUST 先落 G6 门禁
再落生成路径，顺序反了等于把闸门修在洪水之后」**。本轮 `DESIGN-28`（G3 固化管道，
产模板的那一条）与 `DESIGN-31`（G6 生产渲染门）同时就绪，卡号序应取 28。

取 31 的理由：28 一旦落地，注册表里就开始有模板、生产路径就有了消费方；
若此时门还没有，任何一条「先临时用 html 渲染一下」的接线都能悄悄成立，
而它一旦成立就会长出依赖。门先立着，28 落地时只有一条路可走。

**这是排序上的偏离，不是范围上的**：两张卡都在本阶段做完，DAG 依赖未被绕过
（28 与 31 互不依赖，都只依赖 DESIGN-30/02，均已 verified）。已在 progress 的
`started` 事件 note 里写明。

## 2 关键设计判断

**白名单，不是黑名单**：判据只有一条——输入必须是**注册表里的一条记录**，
而不是「一段看起来合规的 HTML」。任何「检查一下就放行」的实现都是黑名单，而黑名单永远漏。

落到接口上：`ProductionRenderer.render` **根本没有接受 html 的参数**。
测试用 `inspect.signature` 断两条路径的入参形状本就不同（探索收 `html`、
生产只收 `template_id`）——这条比任何运行时检查都硬：不是「检查了一下」，
而是那个口子不存在。

**四种「不算已注册」**：别人的模板（D7 按 owner 分）、停用的模板、
**被改过的模板**（内容与 checksum 对不上 = 有人绕过注册流程改了它，
下游会拿到「版本号没变、内容已变」的产物）、不存在的 id。

**插槽两侧都对齐**：少给值拒绝（NEVER 把 `{{block:b-1}}` 原样渲染给客户看）、
多给值也拒绝（那说明调用方以为自己在填另一个模板）。

**探索期照旧无约束**：这道门只管生产路径，`ExploreRenderer` 拿到什么画什么（G0）。

## 3 一处「复用不新写」的实测教训

`default_checksum` 初版自己写了一份 sha256[:16] —— 于是 9 条测试当场红：
注册表构造期用的是**契约那份** `template_checksum`，两份指纹对不上，
模板根本建不出来。改为直接调契约那份。

这正是 checksum 绑定要防的形态：两份指纹口径并存时，「版本号没变、内容已变」就成立了
（S2-2 第三条铁律：产物可复现）。

## 4 自审报告（§4.6，本卡 self_review=true）

**①** acceptance ↔ 测试：

| acceptance | 测试名 |
|---|---|
| 任意 HTML → 拒绝 | `test_arbitrary_html_is_rejected`（TypeError：口子不存在）、`test_production_module_never_falls_back_to_raw_html` |
| 已注册模板放行 | `test_registered_template_renders`（插槽全填、无残留 `{{`） |
| （四种不算已注册） | `test_unknown_template_id_is_rejected`、`test_another_owners_template_is_not_visible`、`test_disabled_template_is_rejected`、`test_tampered_template_is_rejected` |
| 两路径共用接口不同实现 | `test_both_renderers_share_one_interface`、`test_explore_renderer_takes_html_and_production_does_not`（签名断言） |
| （插槽两侧） | `test_missing_slot_value_is_rejected`、`test_unknown_slot_value_is_rejected` |
| （探索不受影响） | `test_explore_path_stays_unrestricted` |

**②** 无冻结件偏离：零触碰 `contracts/` 与 `contracts_v04/`；checksum 直接用契约函数（见 §3）。
**③** 无禁用词：两份产出 0 命中。
**④** 复用断言在位：checksum 走契约；注册表用 DESIGN-30 的既有实现，未另建存储。
**⑤** 装载 ≈10k tokens，未超 40k。

## 5 verify

```
$ pytest tests/v04/design/test_prod_render_gate.py -q  → 12 passed
$ pytest tests/v04/design -q                            → 95 passed
$ ruff check . --no-cache                               → All checks passed!（--fix 归位三处 import 排序）
$ mypy --strict flint                                   → 265 source files, no issues
```

## 6 产出

- `flint/design/prod_render.py`
- `tests/v04/design/test_prod_render_gate.py`（12 条）
