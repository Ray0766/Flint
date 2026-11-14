# DOC-01 · 冻结件修订 `Doc.content`（additive 通道 · owner 已裁方案 A）

**卡** `docs/steward/tasks-v041-b2.json#DOC-01` · **cycles 1** ·
**self_review = true** → §6 · **owner_review = true** → §7
**依赖** GAUGE-01 / GAUGE-02（verified）

## 0. 顺序做倒了，如实记在最前面

worker.md §4.2 写的是**先写失败的测试再实现**。本卡我**倒过来了**：
先改 `contracts_v04/models_v04.py`，再写 `tests/v041/test_doc_content_contract.py`。

补救与补救的边界：

- **做了什么**：变异考①「把本卡的增量整段回退」，实测 **10 failed / 3 passed**
  ——判据确实认得出「这四个字段不在」。
- **它证明了什么**：判据不空转。
- **它 NEVER 等于 test-first**：先写测试逼的是「先想清验收长什么样」，
  回退重跑只能证明「写完之后这份判据有区分力」。**两者不是一回事**，
  所以这一条留在 trace 最前面，而不是藏进变异考表格里。

## 1. 装载清单

卡面 DOC-01 · `contracts/models.py#Doc` 全文 · `contracts_v04/models_v04.py#Doc` 全文 ·
`tools/check_frozen_additive.py` 的 docstring 与比对口径 · `docs/待办-优先级清单.md#D`。
约 6k tokens，预算 40k 以内。

## 2. 四个字段，各有各的不肯含糊

| 字段 | 标注 | 默认 | 为什么是这个形状 |
|---|---|---|---|
| `content` | `str \| None` | `None` | **`None` = 还没提取**，不是「这篇没有正文」。写成 `str = ""` 的话两者从此分不开，重跑提取时不知道该跳过谁 |
| `content_sha256` | `str \| None` | `None` | 算的是**截断前**那一份。截断后再算，验证与去重同时失灵——同一篇文章因截断位置不同会算出两个哈希 |
| `content_truncated` | `bool` | `False` | 截断 **MUST 如实标记**。上限 `DOC_CONTENT_MAX_BYTES = 2 MB` |
| `source_file_ref` | `str \| None` | `None` | PDF 一类**原件**的位置。**正文进库、原件进文件**——PDF 二进制塞进 `content` 既检索不了也引用不了 |

**四个都带默认值**：既有构造点一处不用改。
**四个都排在冻结件那批之后**：dataclass 的字段顺序就是位置参数的顺序，
插进中间的话，所有按位置构造 `Doc(...)` 的地方会**静默地把值装错位**——
那种错不报，只是数据错了。判据 `test_the_new_fields_come_after_the_frozen_ones` 钉着它。

**上限写成具名常量**（`DOC_CONTENT_MAX_BYTES = 2 * 1024 * 1024`）而不是散落的字面量：
散着的话，改上限要靠全仓搜一个数字，漏掉的那处会按旧上限截断，
而它截出来的东西照样标着「未截断」。

## 3. 改既有文件：一处

### `contracts_v04/models_v04.py`（v04 工作副本，卡上 outputs 第一项）

- **改前**：`Doc` 到 `fetch_legal_status` 为止（冻结件九字段 + v0.4 增的四字段）。
- **改后**：**追加**一段 v0.4.1 增量（四个字段 + 一段字段说明），
  另在 `DocKind` 之后加一个模块级常量 `DOC_CONTENT_MAX_BYTES`。
  既有字段、顺序、标注**一个字符没动**。
- **为什么非改不可**：卡上 outputs 第一项就是它，owner 2026-08-04 已裁方案 A。

**`contracts/` 本体一字未动**（acceptance②）：它归 PDD 修订通道，不归执行侧。
判据 `test_the_frozen_original_never_grew_these_fields` 反向钉着——
本体里出现这四个名字中的任何一个即红。

**additive 双通过**（实跑）：

```
python tools/check_frozen_additive.py contracts/models.py contracts_v04/models_v04.py
  → 保留 87 类 / 443 字段 / 1 函数签名 / 31 别名；新增 17 类、18 字段、10 成员  exit 0
python tools/check_frozen_additive.py contracts/protocols.py contracts_v04/protocols_v04.py
  → 保留 24 类 / 1 字段 / 40 函数签名；新增 0  exit 0
```

### 顺带刷新的两份生成物（不是「改代码」）

`assets/gauge_map.json` 与 `docs/尺子清点-v041.md` 由 `python tools/gauge_map.py` 重生成。
**为什么会过期**：本卡的新测试文件也起 `check_frozen_additive.py`，
于是 `SCHEMA-00` 那两条 acceptance 的 `gate_evidence`（「被哪些测试起起来」）多了一项。
`test_disk_copies_are_current` 逐条比落盘副本与实况，当场判红——
**那条判据工作得很好**，它要的就是「盘上那份别过期」。重生成后 104 卡 / 169 条 acceptance：
在门内 110、有尺子但不在门内 59、查不到尺子 0。

## 4. 变异考：十三个，零存活

| 变异 | 抽掉什么 | 结果 |
|---|---|---|
| ① **把本卡的增量整段回退**（重建红基线） | 全部 | **10 failed** ✓ |
| ② `content` 标注改成 `str` | 「还没提取」这一态 | **3 failed** ✓ |
| ③ `content_sha256` 去掉默认值 | 增量不破坏 | **3 failed** ✓ |
| ④ 删掉 `source_file_ref` | acceptance④ | **5 failed** ✓ |
| ⑤ `content_truncated` 默认改成 `True` | 默认态 | **2 failed** ✓ |
| ⑥ 上限改回散落字面量 | 一处真相 | **1 failed** ✓ |
| ⑦ 上限改成 256 KB（owner 加码前那个值） | acceptance③ | **1 failed** ✓ |
| ⑧ 不写「`None` = 还没提取」 | acceptance③ | **1 failed** ✓ |
| ⑨ 不写哈希算的是截断前那份 | acceptance③ | **1 failed** ✓ |
| ⑩ 不写「截断 MUST 如实标记」 | acceptance③ | **1 failed** ✓ |
| ⑪ 不写「正文进库、原件进文件」 | acceptance④ | **1 failed** ✓ |
| ⑫ 不写裁决出处 | 可追溯 | **1 failed** ✓ |
| ⑬ 把新字段插到冻结件那批中间 | 位置参数顺序 | **3 failed** ✓ |

十三次变异后 `models_v04.py` 与变异前逐字相同（baseline 13 passed）。

**字段说明那几条判在哪**：判在**本卡那一段注释**里（`_doc_field_comments()`
从 `# —— v0.4.1 纯新增 · DOC-01` 切到类结束），不判整份文件——
整份文件里「截断」「哈希」这些词到处都是，按全文判的话，把这一段整条删掉毫无反应。
这是前三卡反复撞到的同一形状，本卡一开始就按节判。

## 5. verify 与全局门

```
verify_cmd: pytest tests/v041/test_doc_content_contract.py -q → 13 passed
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: no issues found in 288 source files
            pytest -q               → 3067 passed（UI-02 收卡时 3054，本卡 +13）
additive:   两对逐字校验 exit 0（输出见 §3）
```

## 6. self_review

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① 三个字段（`content` / `content_sha256` / `content_truncated`） | `test_the_working_copy_declares_all_four_fields`、`test_each_annotation_is_the_one_the_card_wrote`、`test_all_four_carry_defaults_so_existing_call_sites_keep_working`、`test_the_dataclass_really_constructs_without_the_new_fields` |
| ② 走 additive 通道、`contracts/` 一字不动 | `test_the_frozen_original_never_grew_these_fields`、`test_the_additive_checker_passes_on_both_pairs`、`test_the_new_fields_come_after_the_frozen_ones` |
| ③ 语义写进说明、上限 2 MB、截断如实标记 | `test_the_cap_is_a_named_constant_not_a_scattered_literal`、`test_the_field_notes_say_what_none_means_for_content`、`test_the_field_notes_say_the_hash_is_of_the_original`、`test_the_field_notes_state_the_cap_and_that_truncation_must_be_marked`、`test_the_ruling_is_attributed` |
| ④ PDF 原件单独留位、正文进库原件进文件 | `test_the_field_notes_keep_the_body_and_the_original_file_on_separate_paths`、上表 `source_file_ref` 那一行 |

**② 无冻结件偏离**：`contracts/` 本体零改动（有反向判据）；additive 双通过；
`flint/domain/` · `requirements.lock` · `assets/heldout_questions.yaml` 未触碰；零新增依赖。

**③ 禁用词**：六词 + 列表尾「等」在两个产物文件里 0 命中。

**④ 复用**：additive 校验直接调既有 `tools/check_frozen_additive.py`（NEVER 另写一个比对器）；
字段排在既有增量段之后，沿用 v0.4 那一段的注释体例。

**⑤ 装载预算**：约 6k tokens，未超 40k。

## 7. owner_review：三件要 owner 拍板的

1. **`source_file_ref` 的形态**。卡上写的是「可选 `source_file_ref`」，
   我取了 `str | None`（对象存储 key 或相对路径，由 DOC-02 定）。
   若 owner 要它带更多结构（比如 `{bucket, key, bytes}`），那要改成一个小 dataclass——
   现在改比 DOC-02 落库之后改便宜。
2. **`content_truncated` 默认 `False`**。`content=None` 时 `False` 是对的
   （没内容就谈不上截断）。风险在于 DOC-02 写入时忘了置位——
   那一层的守卫属 DOC-02 的 acceptance③，本卡只在契约层写明语义。
   owner 若要契约层就把这条钉死，那需要一个 `__post_init__` 不变量检查
   （而冻结件的 dataclass 现在都没有），**那是形态改动，需要 owner 点头**。
3. **2 MB 上限**。owner 2026-08-04 已由 256 KB 加码到 2 MB，本卡照此落值。
   实际存储代价要等 DOC-02 灌真数据才看得出。

## 8. 登记未做

1. **只改了契约，一行运行时代码都没动**。迁移、抓取管线写正文、截断与去重
   全在 **DOC-02**；证据卡吃正文在 **DOC-03**。
2. **`contracts/` 本体没同步**。按 acceptance②，本体的修订走 PDD 通道，
   由 owner 在合适的时候合并 v04 副本的增量——本卡 NEVER 代劳。
3. **没有 `__post_init__` 不变量**：契约层现在挡不住「截断了却没标记」，
   那一条靠 DOC-02 的写入路径守。见 §7 第 2 条。
