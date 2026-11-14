# LOCALE-FORM-OVERFLOWS-ON-MOBILE · 语言与地区表单在 390px 视口横向溢出

**状态** closed · 2026-08-06 · `FIX-05` · **发现者** worker / LOC-01 视觉取证 · **发现时间** 2026-08-05
**危害** 低（能用，但要横向拖）· **改动面** `web/` 的样式，在 LOC-01 outputs 之外

## 实测

```
C:\pwenv\Scripts\python.exe scripts/ui_probe.py --url http://localhost:3000/settings/locale --theme dark --json

desktop  viewport=1440  scroll_width=1440  overflow=False  console_error=0
mobile   viewport=390   scroll_width=438   overflow=True   console_error=0
```

超出 48px。溢出的是表单那一行——`系统语言[中文] 地区[CN] [保存]` 三件套**不换行**。
页头是会换行的（`账户` 已经掉到第二行），所以问题在 `.locale` 这一层的排版。

## 不是 LOC-01 改出来的（已实测排除）

把页面临时改回「前端自带九区」的渲染形态再量一次：

```
改前形态: mobile scroll_width=438 overflow=True     ← 与改后逐字节相同
```

**改前改后同一个数**。地区清单从哪来不影响这一行的宽度：
九个选项的文字都是两个字母，`<select>` 的宽度没变过。

## 为什么现在才看见

此前的视觉取证（`EYE-03` 那张表）只跑了三屏、且没跑 mobile 视口。
`/settings/locale` 这一屏**从来没有人在 390px 下量过**——
这条不是新坏的，是**新被看见的**。

## 给下一张卡

`.locale` 那一行加 `flex-wrap` 或改成纵向排布即可（一行样式）。
顺带值得问的是：**其余十几屏在 390px 下有没有同样的事**？
本单只报了一屏，因为只量了一屏——`ui_probe` 默认就跑 desktop + mobile 两个视口，
把全部屏各跑一遍是一张独立的卡。

---

## 关闭（`FIX-05` · 2026-08-06）

**本单猜的地方不是溢出的地方。** 上面那句「溢出的是表单那一行——三件套不换行」
与「`.locale` 那一行加 `flex-wrap` 即可」**都是错的**，照着改会白改：
`.locale` 至今没有任何样式规则（`locale__*` 那些类名在 `globals.css` 与 `_ds` 里
一条都查不到），它的宽度正好等于视口。

逐元素量下来，越界的只有一个：

```
MAIN    .app-shell__body   right=438  width=438   ← 越界的是它
SECTION .screen            right=414  width=390
SECTION .locale            right=414  width=390   ← 本单怀疑的这个
```

根因算得出来：

```css
.app-shell__body {
  inline-size: 100%;      /* = 390 */
  padding: var(--sp-5);   /* = 24，且默认 content-box */
}
```

390 + 24×2 = **438**，与本单实测的 48px 溢出量对得上小数点。
修法是那一行 `box-sizing: border-box`。

**改后实测**：

```
desktop viewport=1440 scroll=1440 overflow=False err=0
mobile  viewport=390  scroll=390  overflow=False err=0
```

## 这条溢出不止一屏

`.app-shell__body` 是**所有屏**共用的容器——这条溢出十三屏全有，
只是此前只有 `/settings/locale` 在 390px 下被量过。修容器等于一次修掉全部；
全量逐屏取证是 `FIX-06`（本单末尾那句「其余十几屏有没有同样的事」的答案：
**有，同一处**）。

## 留给下一个人的一句

**能对上小数点的算式，比一句「大概是没换行」值钱得多。**
本单当初写的是后者，于是把下一个人往错的地方指了一次。

