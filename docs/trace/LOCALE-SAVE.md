# LOCALE-SAVE · 详情屏的保存按钮，按下去真的存

**结论**：`onSave` + 真三态接上；写回走 `SHELL-01` 建的 `putLocaleAxis`
（**一处定义他处引用**）；只发改过的那一根轴；失败 NEVER 回滚。
`verify_cmd` **8 条全绿**，含一条**真浏览器**往返与一条打真栈的 HTTP 往返。

装载：`docs/steward/tasks-v041-b10.json#LOCALE-SAVE` ·
`web/app/settings/locale/page.tsx` · `web/components/locale-settings/LocaleSettings.tsx` ·
`web/components/shell/localeClient.ts` · `docs/trace/SHELL-01.md`
（实测装载 ≈ 14k tokens，预算 40k）

---

## 1 改前：按钮在，按下去什么都不会发生

页面渲染组件时写着 `status="idle"` 这个**字面量**，且**没有传 `onSave`**。
组件早就备好了 `onSave?` 与 `idle|saving|error` 三态——缺的只是页面这一半。

这与组件文件头那句话是同一种形状：
「回滚之后屏上是旧值、没有报错，**用户会以为自己没点到**」。

`SHELL-01` / `SHELL-02` 之后右上角三根轴早就能存了，唯独这一屏的按钮是死的——
而两处存的本该是同一份 `prefs`。第 9 批的 `SHELL-02` trace §9 就记着这件事，
本卡是那条留言的兑现。

## 2 三处落地

| 事 | 落法 | 为什么 |
|---|---|---|
| 写回 | 走 `putLocaleAxis`（`SHELL-01` 建的） | **一处定义他处引用**。新写一份 fetch 的话两份会各自漂移，而漂移那天右上角与这一屏存的就不是同一份 `prefs` |
| 只发改过的那根 | `draft[axis] !== saved[axis]` 才发 | 原样回写一次会**覆盖另一台设备上刚改的那根轴**；后端 `set_prefs` 的口径本来就是「只改传进来的那一项」 |
| 失败 | `status="error"` + 文案，**NEVER 动 `draft`** | 回滚之后屏上是旧值、没有报错——他会再点一次，然后再失败一次 |

## 3 判据里最要紧的两条

**阴性对照**（acceptance⑤）：把 `onSave` 摘掉 → 判据红且点名「按下去没反应」。
NEVER 只断言「代码里有 `onSave` 这个词」——那种判据在 `onSave={undefined}` 面前照样绿。
对照**改在临时目录里跑**，真文件一个字不动。

**真浏览器那一条**：源码层只能证明「代码里接上了」，
一个 `onSave={() => {}}` 也能过。所以真按一次：

```
options           = ['AU', 'CN', 'FR', 'GB', 'IT']
before            = CN
picked            = AU
button_text       = 保存
status_after_save = idle          ← 没卡在 saving
after_reload      = AU            ← **刷新之后仍是刚选的那个 = 真存住了**
```

改前这一步必红。探针把 demo 的 `region` 改成了 `AU`，跑完**已复位成 `CN`**
（`DEC-045` 本版只做中国区，留一个 `AU` 会让 owner 打开就看到空）；`theme` 一并复位。

**失败那条判两个方向**：失败分支里 NEVER 有 `setDraft`，**且** MUST 把错误交出去。
只判前者的话，一个「失败了什么都不做」的实现也能过——
而那与回滚一样坏：屏上是新值、没有报错，用户以为存上了。

## 4 我自己写错的一处

`catch` 那条判据切得太贪：`code[code.index("catch"):]` 一路切到文件尾，
把 JSX 里 `onChange` 那句 `setDraft` 也圈了进来，
于是报「失败分支把草稿改回去了」——**而那句 `setDraft` 与失败无关**。
改成只切 `save()` 这一个函数。

## 5 改前 / 改后 / 为什么非改不可

| 文件 | 改前 | 改后 | 为什么 |
|---|---|---|---|
| `web/app/settings/locale/page.tsx` | `status="idle"` 字面量、无 `onSave` | `useState` 三态 + `onSave` + 只发改过的轴 + 失败不回滚 | §1 §2 |
| `tests/v041/test_locale_save.py` | 不存在 | 8 条（含阴性对照与两条真栈） | 卡面 |

**组件一行没动**：它三态与 `onSave?` 早就备好了，缺的只是页面这一半。

## 6 自审（`self_review=true`）

**① 判据覆盖 acceptance**（五条）：①实况已钉（`status="idle"` 与无 `onSave` 各一条）；
②接上 `PUT` 且状态真实；③失败不回滚**两个方向各一条**；
④与右上角同一份 `prefs`——打真栈 `PUT` 再 `GET`，且断言**没改的那根没被覆盖**；
⑤阴性对照摘掉 `onSave` 判据红。
**先红后绿**：8 条里 5 条在改页面前红。

**② 无冻结件偏离**：四件未触碰。**③ 无禁用词**：0 命中。
**④ 复用断言在位**：判据钉着页面用 `putLocaleAxis` 且**自己不发 fetch**。
**⑤ 装载未超预算**：≈14k / 40k。

## 7 门

```
pytest tests/v041/test_locale_save.py -q   8 passed（含 1 条真浏览器 + 1 条真栈 HTTP）
ruff check . --no-cache                    All checks passed!
npx tsc --noEmit                           0
npm test -- --run                          858 passed
```
