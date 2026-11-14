# SHELL-02 · 白天/夜间三态切换（`DEC-047` / `DEC-050` 解阻）

**结论**：主题作**第三根正交轴**存进 `prefs`（迁移 `0026`）；右上角三态控件；
**首帧就是最终主题**（实测 `data-theme=dark` 且那一刻 React **还没水合**）。
`verify_cmd` 23 条全绿（含 6 条真浏览器）；`ruff` / `mypy 318` / `tsc 0` / `vitest 857` 全绿。

装载：`docs/steward/tasks-v041-b9.json#SHELL-02` · `DECISIONS-v04.md#DEC-047 #DEC-050` ·
`docs/blocked/SHELL-02-OUTPUTS-CANNOT-REACH-THE-PREFS-COLUMN.md`（本卡关掉的那张单）·
`web/public/_ds/*/tokens/colors.css`（`DARK-01` 的双通道）· `web/app/layout.tsx`（只读）·
`flint/profile/prefs.py` · `flint/api/settings.py` · `docs/trace/SHELL-01.md`
（实测装载 ≈ 30k tokens，预算 40k）

---

## 1 `DEC-050` 解开的是什么

上一轮我按本批 rules 停下开单、**一行代码都没写**，owner 逐字答复「**那是对的行为**」，
并把 outputs 扩到 `migrations/` 与 `flint/`（`profile/prefs.py` + `api/settings.py`）。

**不按设备存的理由**（`DEC-050` 原话，已逐字进 `DECISIONS-v04.md`）：
「夜里用手机、白天用台式机想要的不一样」这个真实需求，
**三态里的「跟随系统」已经覆盖了**——选「跟随系统」的人每台设备各跟各的系统走；
显式选了亮或暗的人，是在说「我到哪都要这个」。

## 2 第三根轴，一条路走到底

| 层 | 改了什么 |
|---|---|
| 迁移 `0026` | `prefs` 加 `theme text NOT NULL DEFAULT 'system'`（接 `0025`，不留号不跳号） |
| `flint/profile/prefs.py` | `Prefs.theme` + `_THEMES` + `set_prefs(theme=…)` 越界校验 + `theme_options()` |
| `flint/profile/pgprefs.py` | 读写第三列 |
| `flint/api/settings.py` | `options()` 多一格 · `LocalePatch.theme` · `locale_json` 多一格 · `_invalid` 多判一根 |

**非空 + 默认 `system`**：可空的话读的人分不出「没选过」与「选了跟随系统」——
而这两件事在本卡里恰恰是**同一件**，更没有理由留一个第三态出来。

**越界当场拒**：NEVER 因为它是「显示偏好」就少一道校验——
存进去之后每个读它的人都要再判一次，而总有人会忘。
判据同时断言**被拒的那次写没有改到库里那份**。

**`extra="forbid"` 照旧**：只是多认一个合法键。判据打了一发 `{"nope": "x"}` 确认它仍然 422。

## 3 最容易做错的那一处：「跟随系统」是**移除属性**

| 选择 | `<html data-theme>` | 谁在决定颜色 |
|---|---|---|
| 跟随系统 | **不设**（属性移除） | `prefers-color-scheme` |
| 白天 | `light` | `[data-theme="light"]` |
| 夜间 | `dark` | `[data-theme="dark"]` |

写 `data-theme="system"` 的话，那两条 CSS 规则**一条都不匹配**——
看起来像亮色，**而系统切暗时它不会变**。判据两处各钉一次
（`applyTheme` 里必须有 `removeAttribute`；首帧那段脚本里 NEVER 出现 `system`）。

真浏览器实测：切到「跟随系统」之后 `data-theme` **回到 `null`**。

## 4 首帧不闪：一段在水合之前跑完的同步脚本

主题的真相在服务端，而取那份真相要一次网络往返——**往返回来之前浏览器已经画完第一帧了**。
显式选了「夜间」的话，那一帧是白的然后突然变暗，正是 acceptance⑥ 逐字禁掉的东西。

（「跟随系统」那一态**本来就不闪**：`DARK-01` 的 `prefers-color-scheme` 是纯 CSS，
第一帧就知道该用哪套色。要抢在首帧之前决定的**只有显式选了亮或暗**这一种。）

落地：`themeFirstPaint.ts` 导出一段字符串，由 `AppShell` **渲染在外壳最前面**
（`<body>` 里第一批被解析到的东西），浏览器解析到它的那一刻就把 `data-theme` 放上去。

### 4.1 cookie 是**提示**，不是第二个真相

它只回答「上一次这台设备上，这个人显式选了什么」，由**写服务端的同一段代码**顺手写下，
并在服务端那份到手时**被服务端纠正**——所以两者不会长期分叉，**分叉时服务端赢**。

**清掉它之后用户的选择仍然在库里、换台设备也还在**，丢的只是「首帧不闪」这一个优化。
这正是提示与真相的分界线：**提示丢了只是慢一点，真相丢了是数据没了**。

（`SHELL-01` 那条禁 `localStorage` 的判据禁的是「把偏好存在浏览器里当真相」；
本卡的控件里 `localStorage` / `sessionStorage` 仍然 0 命中，判据钉着。）

### 4.2 实测（真浏览器，`.ui-probe/shell02-theme.png`）

```
options                  = ['system', 'light', 'dark']
after_dark               = dark
first_paint_after_reload = dark        ← 刷新之后第一帧就是暗的
hydrated_at_read         = False       ← **而那一刻 React 还没水合**
after_reload             = dark
choice_after_reload      = dark        ← 服务端那份存住了
after_system             = None        ← 「跟随系统」把属性拿掉了
after_light              = light
```

`hydrated_at_read = False` 是这条判据的关键：它证明那个 `data-theme` **不是**
React 渲染出来的，而是那段同步脚本在水合之前放上去的。

## 5 三次红，两次是判据自己的

1. **首帧那条读得太早**：探针在 `wait_until="commit"` 读——那是导航刚提交、
   HTML 一个字节还没解析的时刻，读到的恒是 `null`。
   **量的是「浏览器还没开始」，不是「首帧」**。改到 `domcontentloaded`：
   那时同步脚本跑完了，而 React 还没水合、取数也没回来——正是要量的那一刻。
2. **顺序判据比的是注释**：`assert code.index('"system"') < code.index('"light"')`
   ——文件头那张表里也写着 `light`，于是比的是文档而不是代码。
   改成只看 `export const THEMES` 那一行。**本轮第五次撞上「尺子读了注释」**。
3. **判据没把前提清干净**：端点那条固定用 `shell02-user`，上一次跑把他的主题写成了
   `dark`，下一次跑第一句就红。改成每次跑换一个随机身份。

## 6 改前 / 改后 / 为什么非改不可

| 文件 | 改前 | 改后 | 为什么 |
|---|---|---|---|
| `migrations/versions/0026_prefs_theme.py` | 不存在 | 新增 | `DEC-050` |
| `flint/profile/prefs.py` | 两根轴 | 三根轴 + 越界校验 + `theme_options()` | 同上；可选值**一处真相** |
| `flint/profile/pgprefs.py` | 读写两列 | 三列 | 同上 |
| `flint/api/settings.py` | 认两根轴 | 认三根 | 同上；`locale_json` 从「三样」改成「四样」并写清 NEVER 合成 |
| `web/components/shell/ThemeControl.tsx` · `themeFirstPaint.ts` | 不存在 | 新增 | 控件 + 首帧 |
| `web/components/shell/AppShell.tsx` | 右上角两个下拉 | 三个 + 首帧脚本排最前 | 共用同一个 `.app-shell__spacer` 推到右边（`SHELL-01` trace §10 预告过） |
| `web/components/shell/localeClient.ts` | 两根轴 | 三根轴（`LocaleResponse.theme` **可选**） | 声明成必填会让老录制回放夹具全部失效 |
| `web/messages/{zh,en}.json` | — | 各 +4 条 | 三态各一句 + 标签 |

**没碰** `web/app/layout.tsx`（不在 outputs 里）——首帧那段脚本走的是
`AppShell`（本来就由 layout 渲染）这条既有路。

## 7 自审（`self_review=true`）

**① 判据覆盖 acceptance**（六条）：①实况（`DARK-01` 双通道仍在，判据读真 CSS）；
②三态 + 「跟随系统」是显式第一项；③显式压过系统偏好**两个方向各一次**
（CSS 顺序 + 真浏览器切亮/切暗）；④存得住（列非空默认 + 换 store 对象 + 刷新后仍在）；
⑤`DARK-02` 的 `theme-switches` 判据不倒（**子进程真跑那两个文件**）；
⑥首帧不闪（`hydrated_at_read = False` 那一条）。

**先红后绿**：判据先写，实现前 23 条里 9 条红。

**② 无冻结件偏离**：四件一字未动。主题**不进冻结件**——它是显示偏好不是业务词表，
唯一真相在 `flint/profile/prefs.py#_THEMES`（判据断言端点里没抄第二份）。
**③ 无禁用词**：0 命中。
**④ 复用断言在位**：写回走既有 `putLocaleAxis`（`SHELL-01` 建的），
颜色全靠 `DARK-01` 已有的双通道——**本卡一个颜色都没新写**。
**⑤ 装载未超预算**：≈30k / 40k。

## 8 门

```
pytest tests/v041/test_theme_toggle.py -q     23 passed（含 6 条真浏览器）
ruff check . --no-cache                       All checks passed!
mypy --strict flint                           Success: 318 source files
npx tsc --noEmit                              0
npm test -- --run                             85 档 857 passed
两库 alembic_version = 0026
```

真栈实测（重起过的进程 `:8000 PID=5508 Start=16:18:32` / `:3000 PID=55616 Start=16:18:34`）：

```
GET  /settings/locale          → {"lang":"zh","region":"CN","theme":"system", options.theme:[dark,light,system]}
PUT  {"theme":"dark"}          → theme=dark
PUT  {"theme":"neon"}          → 422
```

探针写进 demo 的 `region` / `theme` **已复位**（`CN` / `system`）——
`DEC-045` 本版只做中国区，留一个 `AU` 在那儿会让 owner 打开就看到空。

## 9 留给下游

1. **单据 `SHELL-02-OUTPUTS-CANNOT-REACH-THE-PREFS-COLUMN.md` 由本卡关掉**。
2. **`/settings/locale` 详情屏仍然存不了**（`SHELL-01` trace §10 记过的既有缺陷）：
   它只有草稿态、没有 `onSave`。右上角三根轴现在都能存，**详情屏那个保存按钮按下去仍然没反应**——
   本卡没有动它（不在 outputs 里）。建议给它一张卡。
3. 主题那一列**没有进冻结件**，这是刻意的（§7②）。
