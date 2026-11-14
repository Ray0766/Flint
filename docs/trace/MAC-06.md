# MAC-06 · 缺 `.ui-probe/` 产物时口径统一（@2026-11-14）

出处：`docs/trace/MAC-02.md` §三乙类。起点：68 条红，分布在 16 个判据文件里。

## 一、装载清单

16 个判据文件里报红的 33 个测试函数的函数体开头，与它们用到的读取辅助函数
（`_rows` / `_smoke` / `_nav_snapshot` / `_recorded_ds_reports`）· 各文件的 `PROBE` / `REPORT` /
`SMOKE` / `BEFORE` 常量 · `docs/macOS-安装.md` 第六节 · `.gitignore:21`。

## 二、看到的是什么

同一个文件里两种口径并存。以 `tests/v041/test_eye04.py` 为例：

- 读 `report.json` 的那些判据走 `_report()`，报告不在就 `pytest.skip("还没取证…")`；
- 判「截图在盘上」的那一条直接 `PROBE.glob(...)` 然后 `assert matches`。

报告和截图是同一次取证产出的，要么都在要么都不在。所以新机器上前一半 skip（354 条），
后一半红（68 条），说的是同一件事。`docs/macOS-安装.md` 原文写的预期是 skip。

## 三、决定

**口径**（`tools/probe_evidence.py#require_probe_evidence`）：

- 锚点不在——这台机器没跑过这份取证——skip，写明缺哪一份、怎么补；
- 锚点在——取证跑过——守卫是空操作，**缺哪一张照旧由原来的断言判红**。

**锚点怎么取**：「这份取证跑过就一定会有」的那个目录或报告文件。

| 文件 | 锚点 |
|---|---|
| `test_combo_wire`（截图）、`test_eye04`、`test_eye05`、`test_fav_card` | 各自的取证目录 `PROBE` |
| `test_wb_*` 六个 | 各自的报告 `REPORT`（六张卡共用 `.ui-probe/wb/` 一个目录，目录在不说明这一张卡跑过） |
| `test_ui_mainchain`、`test_ui_restyle` | `.ui-probe/fe_smoke.json`（与既有 26 条 skip 同一个锚点） |
| `test_theme_really_switches` | `.ui-probe/`（`_ds` 取证）与 `theme_switch.json` |
| `test_palette_onscreen`（清点） | `palette/inventory.json` |

**历史对照那一类——6 条——补不回来**：`combo_wire/web_fingerprint.json`（改码前的文件指纹）、
`palette/var-usage-before.json`（换板前的用量）、`tail01/nav-before.json`（搬家前的颜色，3 条）、
`换板前的旧图说明.md`。它们是改动之前拍的，改动已经发生。锚点取那份文件本身，
skip 的话里写明「重跑取证造不出来，只在原来那台机器的 .ui-probe/ 里」。

**没有做的另一种改法**：在 macOS 上另建 playwright 环境、把十几份取证全部重拍。
其中 `combo_wire` 要真调模型，历史对照那 6 条重拍也没用；余下的重拍是另一张卡的量，
而且不改变「新克隆的仓门禁恒红」这件事。登记在 §六。

## 四、判据先行

`tests/v041/test_probe_evidence_guard.py`（24 条）先写：

- 守卫自己：锚点不在 → `pytest.skip.Exception`，话里点名缺的那份与补法；锚点在 → 不 skip（阴性对照）；
- 21 处函数逐个判「函数体第一句就是守卫」（用 AST，写在读盘之后的守卫不算）。

实现前：collection error（`tools.probe_evidence` 不存在）。实现后：24 passed。

**「取证在而缺图仍红」实测过**：建一个空的 `.ui-probe/eye04/`，
`test_eye04::test_every_screenshot_is_on_disk` → `6 failed`；删掉目录后回到 skip。

## 五、验证

乙类 16 个文件 + `test_theme_toggle`：`204 passed, 237 skipped`，新口径的 skip 逐条相加正好 68。
`test_theme_toggle::test_the_dark_palette_ruler_still_stands`（`MAC-04` 留下的那条）随之转绿。

全量 `pytest -q`（单跑，304 秒）：`2 failed, 5403 passed, 422 skipped`。
两条红是 `MAC-03` 往 `pyproject.toml` 里写了 `playwright` 字样造成的，与本卡无关，
当场改掉（见 `docs/trace/MAC-03.md` §六），那两条与 `fe_smoke` 一族重跑全过。
**改掉之后没有再跑全量**，下一张卡收尾时那一遍会看到最终树。

起点的 82 条红至此的去向：环境 6 条绿（`MAC-05`）· 判据自身 8 条绿（`MAC-04`）· 缺产物 68 条 skip（本卡）。

## 六、登记：在 macOS 上重拍取证还没有做

422 条 skip 里绝大多数在等两样东西：一个装了 playwright 的隔离环境（判据里写死的位置是
`C:\pwenv\Scripts\python.exe`，macOS 上没有对应物），和各取证脚本在真栈上各跑一遍。
这是一张独立的卡的量，本卡没有开。
