
**状态** closed · 2026-08-04 · `DARK-01`
> **已关闭 · 2026-08-04 · 由 DARK-01 解决**
>
> owner 2026-08-04 裁决「允许暗色」。`_ds` 的 `tokens/colors.css` 已补一整套暗色板
> （双通道：`prefers-color-scheme: dark` 与 `data-theme="dark"`，后者压过前者），
> 逐 token 覆盖 100%，对比度不低于明色（ink/paper 15.17:1 vs 明色 12.68:1）。
> 判据在 `tests/v041/test_dark_palette.py`，取值依据逐档写在 `docs/trace/DARK-01.md`。
>
> **下面是关闭前的原文，原样保留**——它记着「假绿」是怎么被发现的。

# DS-NO-DARK-PALETTE · `_ds` 只有一套明色，「明暗两主题值不同」这条 acceptance 做不到

**发现者** worker / FB-01 接线时回源核对 · **发现时间** 2026-08-04
**危害** 低中 —— 不影响接线本身；影响的是「主题切换」这件事在 v1 里能不能声称做到
**改动面** 需要**新造一套暗色调色板**（设计决定 + 动供应商资产）→ NEVER 由接线卡自决

## 卡面怎么写的

`FB-01` acceptance②：「断言 token 在运行时真的生效：取 `--background` 等 token 的计算值，
**明暗两主题下取到的值不同**且与 `_ds` 里声明的一致」。

## 真件是什么（四点实测）

1. `grep -rl "prefers-color-scheme\|data-theme\|\.dark" web/public/_ds/…` → **零命中**；
2. `web/` 下（除 `node_modules`）同样**零命中**——全仓没有任何暗色声明；
3. `tokens/colors.css` 是一整套「纸与墨」**明色**：`--paper:#EDEEE6`、`--surface:#F7F8F3`、
   `--ink:#1B2A2E`、`--rule:#D2D6C9`…… 没有任何暗色对照值；
4. 卡面点名的 `--background` 在 `_ds` 里**不存在**——那是 shadcn 的命名习惯，
   `_ds` 用的是 `--paper` / `--surface` / `--ink`。

**旁证**（EYE-03 首跑留下的字节级证据）：接线之前，三屏的 dark 与 light 截图
**逐字节相同**（sha256 前缀两两一致）。当时的解释是「没有样式可切」；接线之后
样式有了，但**仍然只有一套值**，所以「两主题值不同」依旧不成立——只是原因从
「没样式」变成了「只有一套色」。

## 为什么不自己造

- 调色板是**设计决定**：暗色不是把明色取反，它要重新定墨与纸的关系、重定三个性格色
  （`--indigo` / `--sulfur` / `--rust`）在暗底上的可读性，还要过对比度（`tools/visual_assert.py`
  的 AA 4.5:1 判据现成可用）。这是设计的活，不是接线的活。
- `_ds` 是**供应商资产**（终检 C6 的口径：本地改动要单独留痕，否则下次重新导出会被覆盖且无人察觉）。
  在里面加一套色，等于把它变成我们自己的分叉。

## 本卡实际做到的

- acceptance① ③ ④ 全做（接线、无外部字体、既有前端测试不倒）；
- acceptance② **做到了它可做的那一半**：token 在浏览器里取到的计算值与 `_ds` 声明逐条相等
  （`tests/v041/test_ds_wired.py::test_the_tokens_are_live_in_the_browser_with_the_declared_values`）——
  这一半才是「NEVER 只断言 import 语句存在」要的东西；
- 做不到的那一半登记在此，并配一条**自己退休**的断言
  （`test_the_dark_palette_gap_stays_registered_until_the_ds_grows_one`）：
  `_ds` 里一天没有暗色声明，这份问题单就一天不许消失；有了就自动放行。

## 需要 owner 定什么

三选一：

1. **v1 不做暗色**——把「主题切换」从 v1 范围里明确划掉，`scripts/ui_probe.py` 的双主题取证
   降级为「两次取证应当一致」（现在它默认两主题各跑一遍，得到的是两份相同的图）；
2. **让设计侧出一套暗色 token**，走 `_ds` 重新导出（本地不分叉）；
3. **在应用层加一层暗色覆盖**（`web/app/globals.css` 里写 `@media (prefers-color-scheme: dark)`），
   代价是应用层出现一套 `_ds` 之外的颜色真相——与「设计系统是唯一真相」相抵，**不推荐**。
