# MAC-04 · 8 条判据自身的问题（@2026-11-14）

出处：`docs/trace/MAC-02.md` §三丙类 pytest 那八行。起点：8 条在 macOS 上全红。

## 一、装载清单

八个判据文件里各自报红的那一段 · `tests/v041/test_tsc_clean.py:53-64`（`npx` 调法的既有先例）·
`tools/gauge_map.py:121-165` · `flint/api/deliverables.py:60-66,160-170` ·
`DECISIONS-v04.md:342-400`（061 至 064 的标题行）。

## 二、逐条

| 用例 | 改前 | 改后 |
|---|---|---|
| `test_theme_toggle::test_the_dark_palette_ruler_still_stands` | `["python", "-m", "pytest", …]` | `sys.executable` |
| `test_workbench_persist::test_the_two_workbench_responses_are_typed_now` | `.venv/Scripts/python.exe` | `sys.executable` |
| `test_job_denied_state::test_the_rendering_is_asserted_by_a_real_component_test` | `["npx", …], shell=True` | `shutil.which("npx")`，不经 shell |
| `test_screen_data_refetch::test_the_refetch_really_refires_the_request` | 同上 | 同上 |
| `test_translator::test_the_call_site_is_the_only_one` | 前缀 `flint\\i18n\\translate.py` | 命中路径先 `.as_posix()` 再比；另加一句「一个构造点都没扫到即红」 |
| `test_gauge_map::test_disk_copies_are_current` | `sorted(Path)` | `tools/gauge_map.py` 四处排序改用 `_posix` 键，`assets/gauge_map.json` 按新序重写 |
| `test_m3_058::test_read_and_three_formats` | 靠本机 weasyprint 导不进来得到 503 | 把 `_pdf_available` 钉成 False 量 503 这一支；另加一条量引擎在时回真 PDF |
| `test_decisions_landed::test_the_numbers_continue_the_existing_watermark` | 水位 60 | 水位 64，缺号检查的范围同步到 64 |

## 三、三条假绿（本卡查出来的，原先不在红项里）

搜 `shell=True` 时多出三处同样的写法：
`tests/v041/test_source_columns_attribution.py:194`、`tests/v041/test_add_to_workbench_nav.py:226`、
`tests/v041/test_card_to_analysis.py:238`。这三条只判 `returncode == 0`。
POSIX 上 `shell=True` 配参数列表只执行第一个词，实测：

```
OLD rc 0 stdout '' stderr ''
NEW rc 0 [' Test Files  1 passed (1)', '      Tests  8 passed (8)']
NEG rc 1 （指一个不存在的测试文件）
```

也就是这三条在 macOS 上一直是绿的，而 vitest 一条都没跑。三处一并改成 `_npx()`。
改后它们各自真跑了 vitest 并通过。

## 四、新增判据与验红

| 判据 | 守什么 | 怎么验的红 |
|---|---|---|
| `test_gauge_map::test_file_order_does_not_depend_on_the_platform` | 大小写不同的两个文件名按逐码位序排 | 把 `_posix` 改成 `.lower()` → 1 failed；还原 → 1 passed |
| `test_m3_058::test_pdf_is_served_when_the_engine_is_there` | 引擎在时端点回 `%PDF-` | 把端点那句判断改成恒走 503 → 这条红；还原 |
| `test_m3_058::test_read_and_three_formats`（既有，改了前提） | 引擎不在时回 503 | 把端点那句判断改成恒不走 503 → 这条红；还原 |

## 五、决定与偏离

1. **gauge_map 的排序键取 posix 字符串**，不是 `Path.parts`。副作用：`hotspot-card/` 与
   `hotspot-card-actions/` 这类「一个是另一个的前缀」的目录换了先后（`-` 的码位小于 `/`），
   `assets/gauge_map.json` 因此有 7 处两行对调，全是 `files` 数组内部的顺序，没有一条归类变化。
   `docs/尺子清点-v041.md` 的正文与现算逐字相同，没有重写；
2. **`assets/gauge_map.json` 保持 CRLF 写回**（原文件是 CRLF），diff 只有那 14 行；
3. **`test_m3_058` 没有写成「看本机有没有引擎再决定期望哪个码」**：那样引擎在的机器上
   503 那一支永远量不到。现在两支各有一条，503 那支在哪台机器上都跑；
4. `test_decisions_landed` 的文档串照既有体例补了第十三次（第 17 批落 061 至 064）。

## 六、本卡收尾时的数

`ruff check .` → All checks passed · `mypy --strict flint eval harness` → 371 文件零条 ·
本卡碰过的 12 个判据文件：`3 failed, 202 passed, 10 skipped`。三条红都不是本卡的：

- `test_theme_toggle::test_the_dark_palette_ruler_still_stands`：解释器找得到了，子进程真的跑了
  `test_theme_really_switches.py`，那三条因缺 `.ui-probe/theme_switch.json` 而红——归 `MAC-06`；
- `test_job_denied_state` 两条打真栈的：演示库缺 `m1004-j`——归 `MAC-05`。

## 七、登记：仓库在 iCloud 同步的目录里

跑判据期间 `docs/trace/replay30/` 下冒出 20 个 `2026-07-04 2.md` 这种名字的未跟踪文件。
`~/Desktop` 带着 `com.apple.file-provider-domain-id: com.apple.CloudDocs.iCloudDriveFileProvider`
属性，是 iCloud Drive 同步的；回放与判据反复删写这批文件时 iCloud 留下了冲突副本。
20 个副本逐个与 `git show HEAD:<原名>` 比过字节，全部相同，已删。`.git/` 里没有发现同类副本。
仓库放在哪个目录属 owner 的事，本卡没有动；在搬走之前这类副本还会再出现。
