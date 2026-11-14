# DESIGN-21 trace — 字体自托管（外部字体 URL 清零）@2026-08-03

## 1 装载清单（§2.3）

- `CLAUDE.md#S2+S3`、`worker.md`（§7 事前必审四项）、卡片 `tasks-v04.json#DESIGN-21`；
- context_refs：`WORKORDER-v04.md#5-G`（G27 一行）；
- 前置产物：`web/public/_ds/…/fonts/fonts.css` 与 `tokens/typography.css`（DESIGN-04 挂载）、
  `tools/i18n_scan.mjs`（扫描器写法）、`tools/no_hardcoded_models.mjs`（DESIGN-17 的阴性对照做法）。
- 实测装载 ≈ 7k tokens，未超 40k。

## 2 一次「第一跑就骗过自己」的扫描器缺陷（本卡最值得记的一条）

扫描器写完第一次跑：**0 处，exit 0**。看起来这张卡开箱即绿——但 `fonts.css` 里
明明挂着两条 `@import url("https://…")`。

根因在剥注释那一步：`line.replace(/\/\/.*$/, "")` 把 `https://fonts…` 里的 `//`
当成了行注释起点，**整条 URL 被剥掉**，于是扫描器什么都没看见。
判据改为 `(^|[^:])\/\/.*$`（`//` 前面不能是冒号）后，两处如实报出。

这条与前面几次「解释被当成实现」正好相反：那些是**假红**，这次是**假绿**——
而假绿比假红危险得多，因为没有人会去查一个通过了的检查。
所以本卡另跑了**五条阴性对照**（见 §4），确认这把尺子既认得出违规、也不误伤自托管。

## 3 达成 acceptance 的方式，以及它的代价（DEC-017 + 非阻塞单）

两条外部 `@import` 已从 `_ds` 副本移除，改走 `tokens/typography.css` 里**已声明的回落栈**。

**为什么不能顺手自托管**：自托管要 woff2 **二进制**，取得它们要联网下载——
真实网络属 worker.md §7 的**事前必审**项，NEVER 自行触发；`_ds` 自己的 readme
也写着「Replace with self-hosted woff2 **if the user provides binaries**」。

**代价如实登记**：得意黑（首屏大字）与 IBM Plex Mono（数值）退成系统字体。
只影响视觉观感，不影响数据、判定或导出正确性。单子：`docs/blocked/DESIGN-21-FONTS.md`，
决定：`DECISIONS-v04.md#DEC-017`。

## 4 五条阴性对照（实跑）

| 场景 | 期望 | 实测 |
|---|---|---|
| Google Fonts `@import` | 命中 | exit 1，指出行号与 URL |
| 协议相对 `src: url("//cdn…")` | 命中 | exit 1 |
| 自托管 `src: url("/_ds/…woff2")` | 放行 | exit 0 |
| 只在注释里提到外部字体 | 放行 | exit 0 |
| `data:` 内联字体 | 放行 | exit 0（已经在文件里了） |

## 5 verify

```
$ node tools/no_external_fonts.mjs web   → 外部字体 URL：0 处，exit 0
```

回归：`node tools/scan_ds_assets.mjs web/public/_ds --tabular-nums --no-warn-emoji` exit 0
（DESIGN-05 的两条判据在改动后仍成立）；`npm test -- --run design/ds-mount` 11 passed
（DESIGN-04 的挂载断言仍成立）；前端全套 452 passed / 54 files。

## 6 产出

- `tools/no_external_fonts.mjs`
- `web/public/_ds/…/fonts/fonts.css`（移除两条外部 `@import`，留自托管接法与原因）
- `docs/blocked/DESIGN-21-FONTS.md`、`DECISIONS-v04.md#DEC-017`
