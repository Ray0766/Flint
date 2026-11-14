# 第 15 批完成态报告 · v4 调色板并入 `_ds`（W15）

**日期** 2026-08-12 ｜ **卡** 8 张（DEC-060-LANDING / PAL-01~03 / PLZ-COMBO-01 / JUDGE-TAB-01 / AUD-PACK-01 / SHIP-15）
**交接包** `前端设计/应用前端设计需求/design-handoff/`（owner 2026-08-12 放入）
**闸** `docs/FLINT-V041-B14-DONE`（第 14 批 09:39 落盘）→ 本批开跑

---

## 一、换板对照表（16 个 token，一行一个）

| `_ds` token | 改前值（明 / 暗） | 改后值（明 / 暗） | 来源 |
|---|---|---|---|
| `--paper` | `#EDEEE6` / `#0F1A1C` | `#f2ede4` / `#191612` | v4 `--bg` |
| `--paper-2` | `#E3E5DA` / `#131F22` | `#ece5d7` / `#2c261d` | v4 `--panel2` |
| `--surface` | `#F7F8F3` / `#152225` | `#faf7f1` / `#211d17` | v4 `--panel` |
| `--ink` | `#1B2A2E` / `#EDEEE6` | `#26221c` / **`#f9f0e2`** | v4 `--ink`；**暗色提亮**：v4 原值在 `--surface` 上 13.4 < 明色 14.79，提亮后实测 **14.84** |
| `--ink-2` | `#5A6A6E` / `#A9B5B3` | **`#736a59`** / `#9a8e7d` | v4 `--sub`；**明色压暗**：v4 原值 3.57 < AA 4.5，压暗后实测 **4.58** |
| `--ink-3` | `#8B9799` / `#7E8C8D` | `#8f8574` / `#93887a` | v4 `--unk` |
| `--rule` | `#D2D6C9` / `#2E3F44` | `#ded4c2` / `#393226` | v4 `--line` |
| `--sulfur` | `#E8B93C` / `#F0C95A` | `#d1531f` / `#e8763a` | v4 `--accent` |
| `--indigo` | `#2E4A7D` / `#8AA9DE` | `#d1531f` / `#e8763a` | v4 `--accent`（**与 sulfur 合并**，见下） |
| `--rust` | `#B4472C` / `#E0785C` | `#b03a2e` / `#d4695e` | v4 `--bad` |
| `--moss` | `#6B7A5A` / `#94A585` | `#4f7d43` / `#7fae72` | v4 `--ok` |
| `--sulfur-soft` | `#F6E5B3` / `#3A3320` | `#f6ded0` / `#43301f` | v4 `--accent-soft` |
| `--indigo-soft` | `#DDE3EE` / `#1E2A3E` | `#f6ded0` / `#43301f` | 跟着合并 |
| `--indigo-mist` | `#8FA3C4` / `#5C7099` | `#e39877` / `#95532c` | **算出来的**：accent 与同主题 soft 的逐通道中点（v4 没有这一档） |
| `--moss-soft` | `#E0E4D6` / `#222A22` | `#dddfcf` / `#292e21` | v4 `--ok-soft` 的 rgba **合成到同主题 `--paper`** 上 |
| `--rust-soft` | `#F0DAD2` / `#38241E` | `#ead8ce` / `#37231e` | v4 `--bad-soft` 同上 |

**两处刻意不照抄 v4**（改前值 / 改后值 / 实测比值三样都写在 `colors.css` 里，判据逐条比对）：
明 `--ink-2` 与暗 `--ink`。判据**两个方向各量一次**——v4 原值确实不过线（否则这次偏离是多余的）、改后值过线。

**`--indigo` 与 `--sulfur` 合并**照 v4 原意（它自己写的就是 `a{color:var(--accent)}`，没有第二个性格色）；
`colors.css` 注释里点名这是合并并写明**反悔只需改哪三行**——只判两值相等的话，下一个人会当成手滑「顺手修好」。

**缺一格**：`--warn` 一族没落。卡面要落它，而 `DEC-060` 把 `--warn` 逐字列进「NEVER 引进本仓」的 12 个名字——
两处矛盾，按 `worker.md §1.4` 停下开单（值已算好，定名即可落）。

对比度四条全部实测过线：`--ink/--paper` 明 13.56 暗 15.96 · `--ink/--surface` 明 14.79 暗 14.84 ·
`--ink-2/--paper` 明 4.58 暗 5.61 · 性格色在暗 `--surface` 上 5.65 / 5.65 / 4.77。

---

## 二、本批红过的逐条点名归属（三类分开数）

### 甲 · 判据钉着旧板 / 旧口径（**7 条**，全部重新瞄准，意图一个字没动）

| 红的是谁 | 钉着的是什么 | 怎么改的 |
|---|---|---|
| `test_dark_palette::…hue_family` | 「青绿族」（`b >= r`）——那是「纸与墨」那块板 | 改方向为暖族（`r >= b`），`max-min >= 4` 那半条原样保留 |
| `test_theme_toggle::…ruler_still_stands` | 同一处的回声（subprocess 跑上面那个文件） | 上一条绿了它就绿 |
| `test_theme_really_switches` 的 `FROZEN_FG/BG` | 2026-08-04 那天的两个色号 | 降级成注释里的历史记录，判据改从 `colors.css` 现场解析 |
| `test_ds_wired::…live_in_the_browser` | 「所有页都拿明色声明比」 | **明暗各比各的**（见下：它掩盖了一次假绿） |
| `test_eye04::…one_pill_row`（390 两档） | `NAV-ANIME-01` 那一版「一行」 | 390 改判「折成几行都行，但每一项都在屏内 + 条仍是圆角」 |
| `test_eye04::…opinion_one`（同上） | 同上 | 同上 |
| `test_palette_v4::…零改动`（本批自己新写的两条） | 「换板前后 `web/` 零字节改动」——后面三张卡本来就会改 `web/` | 改判「颜色只有一个来源」：零裸色值 + 只有 `colors.css` 定义颜色 token |

### 乙 · 换板/新卡**真碰坏了东西**（**3 条**）

| 红的是谁 | 真相 | 处置 |
|---|---|---|
| `test_plaza_multiselect_combo` ×2 | `PLZ-COMBO-01` 照卡面把上限 5 引进广场，**打红了 `ENTRY-04` 的既有纪律**（广场选的是热点簇，2~5 数的是证据卡） | 按既有纪律执行（撤掉上限），开单 `PLAZA-UPPER-BOUND-CONTRADICTS-ENTRY-04.md` |
| `nav02` / `mainchain` 共 9 条（vitest） | `PLZ-COMBO-01` 把 `useState` 写在**早退之后** → React「Rendered more hooks than during the previous render」 | 挪到早退之前；858 条全绿 |
| `test_fe_be_parity` 一族 | `JUDGE-TAB-01` 把 href 先存进变量，对账尺子把 `/gate/{}` 读成「前端要而后端没有的 API」 | href **就地拼**（尺子按 `href={…}` 分辨导航与调用），并加一条判据钉住这个写法 |

### 丙 · 判据自己的缺陷（**5 条**）

| # | 判据以为自己在量什么 | 实际 |
|---|---|---|
| 1 | `colors.css` 的四个块 | 行首锚点没带 `MULTILINE`，换板后文件开头多了注释 → 四个块一个都切不出来，55 条整片红 |
| 2 | 「屏里另写了一个 5」 | 扫的是「文件里出现过 5」→ 把既有的 `const FEATURED = 5` 判成违规 |
| 3 | 「提示写死在组件里」 | 扫到的是**我自己的解释性注释**（本仓第十次同类） |
| 4 | 探针量顶栏 | 按记忆写选择器（`.app-shell__nav`），实际是 `.app-shell__nav-link` + `nav.anime-nav` → 量到 0 个链接，六屏恒红 |
| 5 | 探针量到的东西 | `rightmost`/`navRadius` 算了却没写进 `report.json` → 判据 `KeyError`（量到与落盘是两件事） |

### 另记一处**流程上的红**（不属上面三类）

全跑时同时开了两个 `pytest`，两者共用 `flint_test` **互相清空**
（`worker.md §9.1` 逐字警告过的形状）：一次报 `2 failed / 6 errors`
（`column "region" of relation "clusters" does not exist`），单跑立刻全绿。
**贴出去的那一份必须是单跑的**——这一条写在这里，免得下次又拿并跑的数当结论。

---

## 三、工单四项的兑现对照（**三项在开工前就已建成**）

| 工单原话 | 仓里实况（**开工前**） | 本批做了什么 |
|---|---|---|
| ① 主题令牌与导航壳 | **已建成**：`_ds/tokens/colors.css` 明暗双板双通道 · `AppShell`/`AnimeNav` 七入口药丸条 · 三态主题开关 | 只**换值**（16 个 token），双通道与顺序一个字没动 |
| ② 热点广场 | **已建成**：`PlazaCards`/`HotspotCard` + `plaza-combo-bar`（计数 / 建组合 / `need_two`）；2~5 规则在 `flint/topic/create.py:67`，空假设校验在 `flint/api/errors.py` | 补 v4 多出来的两样：**假设输入进同一条栏** + **四态提示**（上限那一样按既有纪律**不做**，开单） |
| ③ 判定台五件 | **已建成**：五条独立路由各自可用（主题列表 / Gate① / 作业进度 / 受众选择 / vibe_pack）；受众三条语义（无默认 / 强制单选 / 不选不能提交）今天就成立；`PackViewer` 已是只读清单 + `not_generated` | 加一条**屏内互链带**（不是路由）；补 v4 的三处说明文字；`sibling_deliverable_id` 冻结件里没有 → 开单 |
| ④ 执行方式 | — | 本轮由 steward 出卡、worker 执行；闸是 `B14-DONE`（已落） |

**这一节的重点是：①②③ 的主体不是本批产出**。本批在它们之上做的是
「换值 / 补两样 / 加一条带 / 补三处文案」——**NEVER 把既有成果记成本批的活**。

---

## 四、五条门（逐字贴出，**单跑**）

```
ruff    All checks passed!
mypy    Success: no issues found in 323 source files
pytest  5716 passed, 2 skipped, 12 warnings in 540.91s
tsc     （无输出 = 干净）
vitest  Test Files 85 passed (85) · Tests 858 passed (858)
```

---

## 五、本批开的五张单（每张都写了两到三种口径与各自代价，**没有自己择一**）

| 单 | 一句话 | owner 要答什么 |
|---|---|---|
| `DEC-060-TEXT-IS-STEWARD-AUTHORED-OPTIONS.md` | `DEC-060` 的文字是 steward 拟的选项，owner 从三组里各选一项 | 措辞照落 / 我另写一版 |
| `WARN-TOKEN-NAME-CONTRADICTS-DEC-060.md` | 卡面要落 `--warn`，而 `DEC-060` 把这个名字列进禁令 | 甲（照卡面）/ 乙（改本仓材料名如 `--ochre`）；顺带：明色 `#a3701c` 实测 **4.01**，够图形不够正文线 |
| `PLAZA-UPPER-BOUND-CONTRADICTS-ENTRY-04.md` | 卡面要广场说出上限 5，而既有纪律禁止广场判这条（同一张卡的 acceptance② 也这么说） | 维持既有纪律 / 要广场也提示（那要先答一个问题，单里写了） |
| `SIBLING-DELIVERABLE-ID-IS-NOT-IN-THE-CONTRACTS.md` | v4 写着两版互链，而冻结件里没有这个字段（`grep -c sibling` → 0） | 甲（开冻结件修订窗口）/ 乙（由 `project_id`+`ledger_version` 推导） |
| `NAV-MASCOT-COLOURS-ARE-A-SECOND-SOURCE.md` | 药丸条与吉祥物自带 26 行写死的色号——**颜色的第二个来源**，早于本批 | 并进 `_ds`（逐个定跟不跟主题翻）/ 认定为品牌固定色并给专门前缀 |

---

## 六、出 outputs 的四处（每处都有理由，逐条列出）

| 文件 | 属哪张卡 | 为什么非改不可 |
|---|---|---|
| `tests/v041/test_ds_wired.py` | `PAL-03` | 它拿明色声明比所有页，掩盖了**换板前那份取证是假绿**（dark 页记的是明色的数）；不改它，那条判据继续绿而证不到东西 |
| `tests/v041/test_eye04.py` | `PAL-03` | 390 那一档钉着 `WB-01` 改之前的屏；不改它，重拍之后恒红 |
| `web/app/projects/[id]/proposal/page.tsx` | `AUD-PACK-01` | 三处文案**不渲染就到不了屏上**，而卡面自己的正向判据要求它们在屏上 |
| `web/app/projects/[id]/topics/page.tsx` + `web/app/globals.css` | `JUDGE-TAB-01` | 互链带**不挂就到不了屏上**；样式与它同批 |

---

## 七、不许碰的线，一条没碰

- `contracts/` 与 `flint/`：本批**一个文件都没改**（`sibling_deliverable_id` 那一条按 `S2-1` 停下开单）；
- **单一颜色来源**：`web/` 下只有 `tokens/colors.css` 定义颜色 token（判据钉着）；v4 那 12 个变量名一个都没进来；
- **29 条路由 / 7 个导航入口**一条不动，没有新建 `/judge` 一类的合并屏；
- 外链字体没引（`tools/no_external_fonts.mjs` 在扫）；零新增依赖；
- 本批**零真实网络**：本机容器 + 本机 Ollama；跑完 `WB-06` 那次重写取证后**立刻停掉 worker**
  （它的 gate1 注的是真 github/arxiv，长期开着等于埋雷）。
