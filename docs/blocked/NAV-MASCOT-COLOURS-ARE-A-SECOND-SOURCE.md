# 药丸导航条与吉祥物自带一族写死的色号（颜色的第二个来源）

**状态** closed · 2026-08-12 · `TAIL-01`（开单人 `PAL-01`，缺陷早于第 15 批）

不阻断。本单登记的是**它在哪、为什么今天不动它、什么时候该并回 `_ds`**。

## 一、实况（`web/app/globals.css`，`NAV-ANIME-01` 第 13 批那一段）

```
--mascot-face: rgb(255 255 255);      --nav-surface: rgba(0, 0, 0, 0.5);
--mascot-ink:  rgb(0 0 0);            --nav-border:  rgba(255, 255, 255, 0.1);
--mascot-blush: rgb(249 168 212);     --nav-shadow:  0 8px 32px rgba(0, 0, 0, 0.4);
--nav-ink-on-dark:  rgb(255 255 255); --nav-ink:     …（明暗各一套，共 4 处）
--nav-ink-on-light: rgb(16 20 24);    --nav-hover-bg: …（同上）
```

共 26 行裸色值，全部集中在这一族局部变量的定义处。

## 二、它与 `DEC-060` 第一条的关系

`DEC-060`：**颜色的唯一来源是 `_ds/tokens/colors.css`**。
这一族是**第二个来源**——它们不在 `_ds` 里，换板时不会跟着变。

实测这一点：`PAL-01` 换板之后，广场那条药丸条的底与描边**没有跟着换**
（它们本来就写死在 `globals.css` 里）。屏上看不出「哪一层没跟上」，
只会显得那条导航条与其余部分不是同一套颜色。

## 三、为什么本批不动它

1. **它早于本批**：第 13 批 `NAV-ANIME-01` 照蓝本做药丸条时落的，
   `PAL-01` 只是第一次把「零裸色值」这条判据装上，于是它现形；
2. **改它要先答一个问题**：这一族里有几个是**有意与主题无关的**
   （吉祥物的白脸与黑眼睛在明暗两主题下都该是白与黑），
   而 `_ds` 的 token 是**跟着主题翻**的。把它们并进 `_ds` 之前，
   要先定「哪几个跟主题翻、哪几个恒定」——那是一次设计决定，不是搬运；
3. 本批 outputs 不含 `globals.css` 的那一段（`PAL-01` 的 outputs 只有 `colors.css`）。

## 四、现在怎么守着

`tests/v041/test_palette_v4.py::test_no_component_hardcodes_a_colour`
按名字登记了这一族，**这一族之外再多一个裸色值就红**。
白名单本身也判：这张单不在盘上时那条判据直接红——
**白名单没有单子就是筛子**。

## 五、需要 owner 的什么

一句话即可（不急）：
**甲**——把这一族并进 `_ds`（届时要逐个定「跟主题翻还是恒定」）；
**乙**——认定它们是「与主题无关的品牌固定色」，那就该有一个专门的命名前缀
（例如 `--brand-*`）与一句写在 `_ds` 里的声明，而不是散落在 `globals.css` 里。


## 关闭（`TAIL-01` · 2026-08-12）

owner 2026-08-12 取**甲**：并进 `_ds/tokens/colors.css`，**明暗各一套**，
`globals.css` 只留 `var()`。边界逐字是「**搬的是位置不是值**——
判据断言搬前搬后两主题下 computed color 逐个相等，NEVER 借这次搬家顺手调色」。

### §三那个「先要答的问题」，答了

「哪几个跟主题翻、哪几个恒定」——按它们**今天的实际行为**分，不是重新设计：

| 恒定（只在 `:root` 一次） | 跟主题翻（四个块各一份） |
|---|---|
| `--mascot-face` / `--mascot-ink` / `--mascot-blush`（蓝本的美术设定：白脸 / 黑眼 / 粉腮红） | `--nav-surface` / `--nav-border` / `--nav-shadow` |
| `--nav-ink-on-dark` / `--nav-ink-on-light`（给 `--nav-ink-active` 取用的两端） | `--nav-ink` / `--nav-ink-active` / `--nav-hover-bg` |
| `--mascot-shadow`（引用 `--nav-border`，故随主题走而自身只定义一次） | |

这不是一次设计决定：改前 `globals.css` 里就是这么分的（前五个只在 `:root`，
后六个在明暗两套里各写一份）。**搬的是位置不是值**这句话因此站得住。

### 26 行的去处

`PAL-01` 数的 26 行 = **25 处定义** + 吉祥物那圈描边里的 1 个裸 `rgba`
（`.anime-nav__mascot-head` 的 `box-shadow`）。后者收成 `--mascot-shadow`，
于是 `web/` 下除 `_ds/tokens/` 之外**一个颜色字面量都不剩**——
`TAIL-01` 为此加了一条全仓判据，且**没有白名单**：
白名单一开，下一个例外就有先例可循（本单原本就是白名单里那一条）。

暗色下整圈描边关掉那条规则（`:root[data-theme="dark"] .anime-nav__mascot-head`）
**留在 `globals.css`**：它是规则不是颜色。

**取证**：`.ui-probe/tail01/nav-before.json` / `nav-after.json`
（真浏览器 · 两主题 × 13 个 token × 6 个元素）+ 四张截图。
`PAL-01` 实测到的那处「换板后药丸条没跟着换」，从此不会再发生。
