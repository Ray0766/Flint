# GAUGE-01 · F-11 修复：PRINCIPLES 漏重映射 + 六把文档尺接进全局门

> v0.4.1 第 2 批首卡。verify_cmd `pytest tests/v041/test_doc_gates.py -q` → **9 passed**。

## 装载清单（实际）

| 来源 | 用途 |
|---|---|
| `worker.md`（全文） | 执行纪律 |
| `docs/steward/连跑工单-v041-第2批.md`（全文） | 本批口径 |
| `docs/steward/tasks-v041-b2.json#GAUGE-01` | 卡面 |
| `tools/check_principles_doc.py`（全文） | 尺子实现 |
| `WORKORDER-v04.md#8`（V0/V1 出口命令两行） | 六把尺子的**规范调用**逐字来源 |
| `tests/v04/principles/test_fixtures_load.py`（全文） | 确认旧 5 条量的是什么 |
| 六把尺子的 docstring 头 + main 签名 | 命令行形态 |

约 22k tokens，未超 40k。

## F-11 的根因链（acceptance ④）

1. `DEC-007` 把前端根从 `web/src/` 重映射为 `web/`；
2. 改到了 `WORKORDER-v04.md#3` 的两条「校验点」（`--run src/components/native-name`、`--run src/components/quote-slot` → 去掉 `src/`），**没改** `docs/PRINCIPLES-v04.md` 的同两行；
3. PRIN-01 的不变量是「落盘文档与工单 §3 正文归一后**逐字节相等**」——这一步破了，`tools/check_principles_doc.py` 从那天起 exit 1；
4. 而全局门是 `ruff && mypy --strict flint && pytest -q`，**六把文档尺一把都不在里面**；
5. 门里能跑到这份文档的只有 `tests/v04/principles` 那 5 条，而它们量的是「反例 fixture 与文档反例段一一对应」——与哈希无关，所以恒绿；
6. 于是 `DEC-019` 当天引用的「5 passed」**是无效证据**：它证明的是另一件事。

一句话：**两把尺子量同一份文档，一红一绿，而门里跑的是绿的那把。**

## 改既有文件（本批 §3 要求逐处写明）

**唯一一处**：`docs/PRINCIPLES-v04.md`，改 8 个字节。

| 项 | 内容 |
|---|---|
| 改前 | 第 37 行 `` `cd web && npm test -- --run src/components/native-name` ``；第 51 行 `` `cd web && npm test -- --run src/components/quote-slot` `` |
| 改后 | 两处的 `src/components/` → `components/` |
| 为什么非改不可 | 这两行就是 `DEC-007` 重映射漏掉的地方。工单侧已经是新写法，文档侧是旧写法；PRIN-01 的判据是两侧逐字节相等，所以**只能改文档去对工单**——反过来改工单会让 §3 正文与 `DEC-007` 已确立的口径矛盾，且 `PRIN-01` 的哈希锚点在工单侧。改后 `check_principles_doc.py` exit 0，sha256=`b1c01ae3a21b021e87a3912f67cb5914588f1eba5ca278698b056836f2180434`。文档为 LF（52 行、0 个 CRLF），字节级替换未改行尾。 |

副作用核查：`src/components` 与 `web/src` 在该文档中改后出现次数均为 **0**；旧 5 条测试（读同一份文档的「反例」段）复跑 **5 passed**，fixture 未重生成也无需重生成——改的是「校验点」段，不在它们的比对面里。

## 新增产物

`tests/v041/test_doc_gates.py`（9 条）：

- `test_doc_gate_exits_zero[×7]` —— 六把尺子逐把 `subprocess` 起来断 exit 0（`check_frozen_additive` 按既有口径跑 models / protocols 两次，故 7 条参数化）。**不重新实现任何校验逻辑**，只让 `pytest -q` 覆盖到它们；
- `test_all_six_gates_are_covered` —— 名单本身也守：漏登记一把尺子等于那把仍在门外；
- `test_tampered_doc_reddens_new_gate_while_old_tests_stay_green` —— acceptance ③ 的构造用例。

## 构造用例为什么改真文件（而不是副本）

旧那 5 条读的是 `docs/PRINCIPLES-v04.md` 这个**固定路径**，改副本证明不了「旧测试仍绿」——那才是这条断言的全部内容。原始字节在 `try` 之前读出、`finally` 写回，用例结尾再断言一次文件已复原且尺子回到 exit 0（三重复原保证）。

篡改点选在「校验点」段而不是随便一行：F-11 就长在这一段，而这一段**不进旧测试的比对面**。选在「反例」段的话两把尺子会一起红，那就没有钉住「一红一绿」这个形态——下次同类漂移仍可能只被绿的那把量到。

## 一处 lint 返工

`ruff PLW1510` 要求 `subprocess.run` 显式给 `check`。这里非 0 退出码是本文件的**判据**而非异常，故显式写 `check=False` 并加行注释说明——不是为过 lint 而加的样板。

## self_review 五条

① **测试真实覆盖 acceptance**

| acceptance | 测试 |
|---|---|
| ① `check_principles_doc.py docs/PRINCIPLES-v04.md` exit 0 | `test_doc_gate_exits_zero[check_principles_doc]` |
| ② 逐把跑六把尺子，任一 exit≠0 即红 | `test_doc_gate_exits_zero[×7]` + `test_all_six_gates_are_covered` |
| ③ 旧 5 条一字不改；构造用例证明「改歪 → 新红旧绿」 | `test_tampered_doc_reddens_new_gate_while_old_tests_stay_green`（旧文件零修改，`tests/v04/principles` 复跑 5 passed） |
| ④ trace 写明根因链 | 本文件「F-11 的根因链」一节 |

② **无冻结件偏离**：

```
additive 校验通过：models_v04.py 保留了 models.py 的全部 87 类 / 443 字段 / 1 函数签名 / 31 别名；新增 17 类、13 字段、10 枚举/联合成员
additive 校验通过：protocols_v04.py 保留了 protocols.py 的全部 24 类 / 1 字段 / 40 函数签名 / 0 别名；新增 0 类、0 字段、0 枚举/联合成员
```

（这两条从此也在 `pytest -q` 里跑——正是本卡的目的。）

③ **无禁用词**：`grep -nE "适当|合理|必要时|大约|尽量|若干" tests/v041/test_doc_gates.py docs/PRINCIPLES-v04.md` → 零命中（exit 1）。

④ **复用断言在位**：本卡零新写校验逻辑，六把尺子按 `WORKORDER-v04.md#8` 的规范调用原样起进程；`test_all_six_gates_are_covered` 断言六个工具文件真存在（编造一把不存在的尺子会红）。

⑤ **装载未超预算**：约 22k tokens < 40k。

## 遗留

`tools/check_impact_doc.py` 与四把 `.mjs` 扫描器（`i18n_scan` / `lint_no_confidence_viz` / `no_external_fonts` / `no_hardcoded_models` / `scan_ds_assets` / `orthogonality_check`）**不在本卡 acceptance 的六把之内**，故未接。F-11 的教训对它们同样成立——登记在此，归 `GAUGE-02` 的清点面。
