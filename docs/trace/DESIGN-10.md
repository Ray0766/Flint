# DESIGN-10 trace — 直接编辑（data-loc 定位 + 落点顺序 + 导出剥离）@2026-08-03

## 1 装载清单（§2.3）

- `CLAUDE.md#S2+S3`、`worker.md`、卡片 `tasks-v04.json#DESIGN-10`；
- context_refs：`WORKORDER-v04.md#5-G`（G14 一行）；
- 前置产物：`web/design/renderer/`（DESIGN-02 零构建）、`web/design/tweaks/tweaks.ts`
  （DESIGN-08 的字节区间回写口径）、`web/test-utils/source.ts`。
- 实测装载 ≈ 6k tokens，未超 40k。

## 2 关键设计判断

**落点顺序是按影响半径排的**：工具类只影响这一个元素、inline style 也只影响这一个、
全局 CSS 影响**所有长得像的**元素。用户点着一张卡片说「这里紧一点」，
改的却是全站所有卡片——那是他绝不会预期的。

**全局 CSS 这条路根本不存在**（不是「排在最后」）：本模块没有那个入参，
也没有任何写 `<style>` / `styleSheet` / `insertRule` 的分支（四个词源码级断言）。
留一个「最后才用」的口子，早晚会有人在某个说不清的场景里用上它。

**顺序是硬的**：两者都给时优先工具类，不由调用方临场决定——让调用方决定就等于没有顺序。

**开标签区间足够小**：`findByLoc` 只回开标签那一段。区间越大，回写时越容易碰到正文；
属性编辑本来就只需要这一段。测试专门断它**不吞正文**。

**导出剥 data-loc**：那是编辑器给自己用的锚。留在产物里等于把开发期的脚手架交付给客户，
而且下一次导入时这些锚会与新的编辑器状态对不上号。剥的时候连同多余空格一起收拾
（`<h1 data-loc="x" class=` 剥完不该变成 `<h1  class=`），单引号与无引号写法也剥得掉。

## 3 一次实现修 + 一次判据修（两者性质不同，分开记）

**实现修（真 bug）**：`applyEdit` 原先只判 `=== null`。于是传一个**根本不存在的落点**
（`{loc, globalCss}`）时，两个字段都是 `undefined`，那道「两个落点都没给」的检查
**静默放行**，编辑照跑。改为 `?? null` 归一后，非法调用如实抛错。
这条正是 acceptance①「全局 CSS 写入路径不存在」要防的形态——测试先红把它逼了出来。

**判据修（测试写错）**：`findByLoc` 的区间断言原本期望它覆盖到正文（`toContain("燧石")`），
而只回开标签才是对的。改断它**恰等于**那段开标签且不含正文，比原判据更强。

## 4 自审报告（§4.6，本卡 self_review=true）

**①** acceptance ↔ 测试：

| acceptance | 测试名 |
|---|---|
| 落点顺序 工具类→style | `顺序表就是两级`、`能用工具类表达就落工具类`、`工具类表达不了才落 inline style`、`两者都给时优先工具类` |
| 全局 CSS 写入路径不存在 | `全局 CSS 写入路径不存在`（非法入参抛错 + 四词源码断言）、`两个落点都没给时报错` |
| 导出产物零 data-loc | `导出产物零 data-loc`、`只剥 data-loc，别的属性一个不动`、`剥离不留双空格`、`单引号与无引号写法也剥得掉` |
| （定位精度） | `按 loc 找到的是开标签且不吞正文`、`loc 不存在时返回 null`、`改动只落在那一个元素上` |

**②** 无冻结件偏离：纯前端模块。
**③** 无禁用词：两份产出 0 命中。
**④** 复用断言在位：字节区间语义与 DESIGN-03/08 同构；源码扫描走共享 `codeOnly`。
**⑤** 装载 ≈6k tokens，未超 40k。

## 5 verify

```
$ cd web && npm test -- --run design/direct-edit  → 14 passed
$ npm test -- --run                                → 384 passed / 48 files
$ npm run typecheck                                → 干净
$ node tools/i18n_scan.mjs web/design --fail-on-cjk → exit 0
```

卡上 cycles=2，实际 1。产出均为 LF。

## 6 产出

- `web/design/direct-edit/directEdit.ts`、`directEdit.test.ts`（14 条）
