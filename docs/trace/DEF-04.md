# DEF-04 · E1 观察项：`scan_ds_assets.mjs` 补目录跳过

**卡** `tasks-v041-b2.json#DEF-04` · **开工** 机器 UTC 2026-08-04T01:53Z

## 1. 装载清单

卡面 DEF-04 · `tools/scan_ds_assets.mjs` 全文 · 另三把扫描器的跳过写法逐字
（`i18n_scan.mjs:42` / `lint_no_confidence_viz.mjs:54` / `no_external_fonts.mjs:38`）·
`docs/v0.4.1-候选清单.md` 的 E1 登记段（DEC-021「封版后不打无卡的补丁」）。约 5k tokens。

## 2. 顺序（§4.2）

测试先落盘先跑红（`5 failed | 3 passed`）→ 实现（walk 里加一行 `continue`）→ 8 passed。
连续第十八张。

## 3. 改既有文件（§4.1，本卡 outputs 之内）

| 文件 | 改前 | 改后 | 为什么非改不可 |
|---|---|---|---|
| `tools/scan_ds_assets.mjs#walk` | 递归到底，不跳任何目录 | 进递归前 `if (entry === "node_modules" \|\| entry === ".next") continue;` + 七行理由注释 | 卡面正题。口径与另三把**逐字**一致：各写各的那天，「跳哪些目录」就有四个版本，而漏跳的那个只有换扫描面时才会发现——正是本条观察项的由来 |

**没有改用 `SKIP_DIRS` 那一族的写法**（`check_vitest_filters.mjs` / `i18n_key_defined.mjs` /
`no_scaffold_on_screen.mjs` 用的是 `new Set([... "dist", "coverage", ".git"])`）：
卡面写的是「与其余三把口径一致」，而那三把用的是两名字的 `continue` 形。
仓里现在确实有两族写法——**这件事本身值得统一，但那是一张新卡的面**，
本卡按卡面对齐，不顺手扩面（登记见 §6-1）。

## 4. 对 `web` 全树实跑（acceptance②）

**改之前**：

```
扫描 14582 个文件（web）
  数字容器缺 tabular-nums：6 处
  代码里的图标字符：2039 处   文档里的图标字符：716 处
  ✗ .next/dev/static/chunks/node_modules_next_dist_compiled_14ibvna._.js:1881 …
  ✗ node_modules/next/dist/compiled/next-devtools/index.js:414 …
```

6 处 tabular 命中**全部**在 `.next` / `node_modules` 底下，`--tabular-nums` 直接判红。
（卡面写的是「4 处」，今天的真实数是 **6 处**——依赖装过之后 vendor 内容会变，
数字对不上不影响结论：命中全是 vendor。）

**改之后**：

```
扫描 163 个文件（web）
  数字容器缺 tabular-nums：0 处
  .num 类带 tabular-nums：在
  代码里的图标字符：1 处      文档里的图标字符：0 处
  ✗ app/globals.css:35 图标字符 ⚠
EXIT=0
```

扫描面 14582 → **163**；tabular 命中 6 → **0**；`--tabular-nums` 退出码 0。

**原目标未受影响**：`web/public/_ds` 双开关仍是 `扫描 11 个文件 / 全 0 / EXIT=0`。

## 5. 剩下那一处 ⚠ 是注释，不是图标（第九次同型）

`app/globals.css:35` 的 ⚠ 在一段 FB-02 的注释里，原话是
「**改之前**用户看得见一个 ⚠，改之后什么都看不见，而测试照样绿」——
它在说明那条 CSS 规则为什么必须存在，不是拿 ⚠ 当图标。

图标那条判据扫的是**原始文本**，不剥注释。所以拿 `--no-warn-emoji` 扫 `web` 会红在这里。

**没有动它**，两个方向都不动：

- 不删注释——那段写着「没有这条规则时视觉那一半完全不存在」，删了下一个人会以为
  这条 CSS 是装饰（DEF-01 §7.5 同款，本批一路在守的就是「判据不该与留痕互相取消」）；
- 不改图标判据的剥离口径——那是另一条 acceptance 的面，本卡只补目录跳过。

登记在 §6-2，修法写清楚了：图标扫描前先剥 `/* */` 与 `//`，口径同
`web/test-utils/source.ts#codeOnly`。

## 6. verify 与 self_review

```
verify_cmd: pytest tests/v041/test_scan_ds_skip.py -q → 8 passed
node tools/scan_ds_assets.mjs web/public/_ds --tabular-nums --no-warn-emoji → EXIT=0
node tools/scan_ds_assets.mjs web --tabular-nums → EXIT=0（见 §4）
ruff check . --no-cache → All checks passed!
```

**① acceptance 映射**

| acceptance | 测试 |
|---|---|
| ① 跳过 `node_modules` 与 `.next`，与其余三把口径一致 | `test_a_violation_inside_node_modules_is_skipped`、`test_a_violation_inside_dot_next_is_skipped`、`test_the_idiom_is_the_same_as_the_other_scanners`（连另三把的写法也一起断言，免得哪天它们先变） |
| ② 对 `web` 全树跑一次并把真实结果写进 trace | §4；`test_scanning_the_whole_web_tree_no_longer_drowns_in_vendor` |
| ③ 扫描器既有的自证用例全绿不倒 | `test_the_original_target_still_passes`（原目标双开关 exit 0） |

**阴性对照**（这把尺子的一半）：`test_the_same_violation_outside_those_dirs_is_still_red`——
「跳过 vendor」与「什么都不扫」在退出码上长得一模一样（都是 0），
所以同一份违规内容挪到 `src/` 底下必须红。另有
`test_the_skip_is_by_directory_name_not_by_path_substring`（`my_node_modules_notes/`
不该被跳）与 `test_the_skipped_dirs_are_not_even_walked`（跳在递归里，不是读完再筛）。

**② 无冻结件偏离**：`contracts/`、`flint/domain/` 未触碰；零新增依赖；改既有文件一处，
在本卡 outputs 之内。

**③ 禁用词**：两个产物文件六词 0 命中、本 trace 收尾「等」0 命中。

**④ 复用**：跳过写法逐字复用另三把扫描器；阴性对照的形状复用 GAUGE-04
（「扫到 0 条即红」同源——都是在防「没扫到」冒充「全都对」）。

**⑤ 装载预算**：约 5k tokens。

## 7. 变异考：三个全红，第三个只被**一条**判据抓住

| 变异 | 抽掉什么 | 结果 |
|---|---|---|
| ① 去掉 `continue` 这一行 | 本卡正题 | **5 failed** ✓（即开工时那份红） |
| ② 改成 `includes("node_modules")` 子串形 | 「按目录名不按子串」 | **2 failed** ✓ |
| ③ 改成读完再筛（walk 照常递归到底，扫描前 filter 掉） | 「跳在递归里」 | **1 failed** ✓ |

**变异③ 的那 1 条是源码面判据**（`test_the_idiom_is_the_same_as_the_other_scanners`），
不是文件计数那条——**计数是筛完之后打印的，两种写法给出同一个数**。

首版把 `test_the_skipped_dirs_are_not_even_walked` 的 docstring 写成
「判据用文件计数：跳过的那些没有进过文件清单」，变异③ 证明那句话是错的。
改名 `test_a_whole_vendor_subtree_stays_off_the_scan_surface` 并把这件事写进 docstring：
**它守的是扫描面，性能那一半由源码面判据守**。留着原话的代价很具体——
下一个人会以为这里已经守住了，然后放心地把 walk 改回递归到底。

三次变异后 `tools/scan_ds_assets.mjs` 的 sha256 与变异前逐位相同。

## 8. 登记未做

1. **仓里有两族跳过写法**：本卡对齐的是两名字 `continue` 形（三把）；另有
   `SKIP_DIRS` 集合形（三把，多跳 `dist` / `coverage` / `.git`，其中两把还跳 `_ds`）。
   统一成一份共享件是**另一张卡的面**——本卡按卡面对齐，NEVER 顺手扩面。
2. **图标判据不剥注释**：见 §5。修法是扫描前先剥 `/* */` 与 `//`，
   口径同 `web/test-utils/source.ts#codeOnly`。本卡未做，因为那是另一条 acceptance 的面。
3. **`web` 全树没有进任何门**：本卡证明了「拿它扫 `web` 不再淹在 vendor 里」，
   但没有把这条扫描加进 CI。加不加属工程决定（扫 163 个文件的成本很低，
   但它会把 §5 那一处注释变成红）。
