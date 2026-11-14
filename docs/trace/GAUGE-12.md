
# GAUGE-12 · 尺子⑥：逐屏组件对照 —— 本仓第一把**正向**尺子

> v0.4.1 第 5 批第十四张。依赖 `PLAZA-01`（verified）。

## 装载清单

`tasks-v041-b5.json#GAUGE-12` · `docs/steward/交接-STEWARD-HANDOFF.md` ·
`docs/review/终检-v04.md#F-11` · `tools/check_design_constraints.mjs`（分工惯例）·
`tests/v041/test_ds_bundle_wired.py`（「零样式判红」的既有技法）·
本批七屏的实际类名与选择器。约 9k tokens，**未超 40k**。

## 一、这批返工的根因就是没有这把尺子

全仓此前的判据**都是禁止性的**：NEVER 空转 / NEVER 空态冒充 / NEVER 硬编码。
它们挡得住做错，**挡不住没做**。

广场屏那四条 `EYE-03` 判据（HTTP 200 · 零控制台报错 · 无横向溢出 · 两主题截图）
**全绿**，而那一屏是个 `ul/li`、全文件零 `className`——它就是这么过去的。
**一屏「什么都没做」在禁止性判据下永远是干净的：它没有错误可犯。**

## 二、三件产物与它们的分工

| 件 | 管什么 |
|---|---|
| `assets/screen_composition.json` | **声明**：每屏 MUST 用到的组件选择器 + MUST 有样式的类名，各带 `why` |
| `tools/check_screen_composition.mjs` | **对账**：声明 vs 观测，三类违规各自成一类 |
| `tests/v041/test_screen_composition.py` | **眼睛 + 门**：用 `C:\pwenv` 的 playwright 落观测，跑对账，配三条阴性对照 |

`.mjs` 在 node 侧跑、**没有 DOM**，所以它消费观测产物。
这与本仓既有的 `check_design_constraints.mjs`（静态）+ `ui_probe.py`（运行时）
是同一套分工：**判据在那边，眼睛在这边**。

## 三、三类违规为什么不合成一类

| kind | 说的是 | 修法 |
|---|---|---|
| `missing_component` | 声明要它，DOM 里没有 | 去把组件接上 |
| `zero_size` | DOM 里有，宽高是 0（`F-09` 的形状） | 去把样式补上 |
| `unstyled_class` | 类名在，**计算样式与裸元素逐条相同** | 同上，但根因在样式表 |
| `not_probed` | 声明了这一屏，取证里没有它 | 去跑取证 |

「没有观测产物」与「有违规」也**分成两个退出码**（`2` 与 `1`）——
共用一个的话，人会照着错的那条去修：一个是去做界面，一个是去跑取证。

## 四、判据的重心：`differsFromBare`

零样式的判法与 `DS-02` 那把尺子同源：铺一个裸元素当基线，逐条比 19 项计算值，
**一样就是「类名在、样式没有」**——改前的广场屏正是这个样子。

## 五、阴性对照三条（`acceptance③` 的原话）

1. **把广场的卡片换回无样式列表** → 必须报 `missing_component` + `unstyled_class`，
   **且报文里指出缺的是哪一个选择器**；
2. **取证里少一屏** → 必须报 `not_probed`（**没量过的屏不算做过**）；
3. **观测产物不在** → 退出码 `2` 且给出「去跑取证」的修法，不与违规混。

没有这三条，「0 处违规」可能只是因为尺子什么都没查。

## 六、接进全局门（`acceptance④`，`F-11` 的教训）

`F-11` 是「两把尺子一红一绿，红的那把没人跑」。所以本卡的判据文件在
`tests/v041/` 下、被 `pytest -q` 的默认收集面收到，并配一条
`test_this_ruler_runs_inside_pytest_q` **实跑 `--collect-only` 确认**
（而不是读源码找 `skipif`——`WIRE-05` 实测过，读源码会判到自己的断言串上）。

## 七、当前实况（真栈跑过）

```
node tools/check_screen_composition.mjs
→ 逐屏组件对照：7 屏 / 34 项声明，0 处违规。

/plaza                            组件 6/6   有样式 6/6
/design                           组件 4/4   有样式 3/3
/projects/[id]/topics             组件 1/1   有样式 1/1
/projects/[id]/analysis           组件 3/3   有样式 2/2
/projects/[id]/proposal           组件 2/2   有样式 1/1
/deliverables/[id]/interventions  组件 2/2   有样式 1/1
/combo                            组件 1/1   有样式 1/1
```

**owner 指认的两屏（广场、设计工作台）判据里钉死必须在册**——它们是本批的由来。

## 八、verify

```
pytest tests/v041/test_screen_composition.py -q → 9 passed
pytest tests/v041 -q                            → 2444 passed / **1 failed**
                                                  （只剩那条 SSE 403，已立单，非本批）
ruff check . --no-cache                         → All checks passed
python tools/check_line_endings.py              → 219 个文件全是 LF
```

零返工：本卡的三件产物都是新建，且「零样式判红」的技法在 `DS-02` 已经验证过一轮。

## 九、self_review（worker.md §4.6）

① **测试覆盖 acceptance**：9 条对四条 acceptance。
主判据是**运行时**（组件被真渲染 + 类名真有样式），
配三条阴性对照证明尺子认得出坏的——**没有它们，「0 处违规」说明不了任何事**。
② **无冻结件偏离**：`contracts/` 一字未动；本卡只新增三件产物。
③ **无禁用词**：grep 零命中。
④ **复用断言在位**：零样式的判法与 `DS-02` 同源（裸元素基线）；
对账器与既有 `.mjs` 尺子同一套分工，NEVER 另起一套观测。
⑤ **装载未超预算**：≈9k tokens。

## 十、留给下游

- 新屏进来时**必须**往 `assets/screen_composition.json` 加一行——
  加不加由人决定，但**不加就等于那一屏可以悄悄退化回结构化文本**。
  这条与 `harness/fe_smoke.py` 的 `SAMPLE_IDS` 是同一道绊线；
- 本卡声明的是本批建/改过的七屏。其余屏（账户、账单、报告查看器…）**没有在册**——
  它们不在本批触碰面内。`GAUGE-13` 的屏对照表会给出全量名单，
  下一批可据它把声明补齐。
