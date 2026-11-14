# GAUGE-08 · 换行符：一个 CRLF 让全仓剥注释的尺子集体失效

**卡** `docs/steward/tasks-v041-b3.json#GAUGE-08` · **cycles 1（oneshot）** ·
**self_review = true** → §5 · **owner_review = false** · **依赖** 无

## 1. 装载清单

卡面 GAUGE-08 · `docs/blocked/CRLF-BREAKS-COMMENT-STRIPPING.md` 全文 ·
`web/test-utils/source.ts#codeOnly` 的剥刀写法 · 全仓行尾统计（实跑）。
约 8k tokens，预算 40k 以内。

## 2. 先量，坐实那张单的推断

单子写的是推断（「同一条缝在另一个方向上会给出假绿」）。开工先量：

```
全仓（含 md/json/yaml）：LF 1637 · CRLF 531 · mixed 5
剥刀实际扫描的那一面（web/**/*.ts(x)，198 个）：LF 163 · **CRLF 35**
```

再拿**真文件**跑一遍那把剥刀（`node`，不是描述）：

```
lib/jobClient.ts      CRLF 161 行   注释 13 处   剥掉 **0** 处
lib/screenClient.ts   CRLF  80 行   注释 26 处   剥掉 **0** 处
```

**坐实了**：那 35 个文件上，所有「源码里不该出现 X」的判据
都退化成了「**全文**里不该出现 X」。

## 3. 尺子只盯**剥刀扫描的那个面**，不是全仓风格

本仓 531 个文件是纯 CRLF（Windows 上的常态）。一刀切成 LF 是一次巨大的
无关改动，且会让所有历史比对失效。

**这把尺子守的不是代码风格，是别的尺子的视力**——所以 `SCANNED_FACES`
只有 `("web", (".ts", ".tsx"))`，并配了一条判据钉住这个范围。

混用（同一文件里两种行尾）**单列一类**：它在任何读法下都有一半行为异常，
且通常是**一次工具事故的痕迹**——`Path.write_text()` 在 Windows 上默认做
换行翻译，`DEF-03` 那次就是这么来的（内容逐字未变，行尾全变了）。

## 4. 修法：只换行尾，内容逐字未变

35 个文件 `\r\n` → `\n`，改前逐个断言
`raw.replace(b"\r\n", b"") == new.replace(b"\n", b"")`——
**只允许行尾变，别的一个字节都不许动**。

修完同一份探针：**剥掉 13 处 / 26 处**（改前 0 / 0）。

## 5. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_line_endings.py -q → 13 passed
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: 299 source files
            pytest -q               → 3830 passed（GAUGE-07 收卡时 3817，本卡 +13）
            cd web && npm test -- --run → 74 files / 750 passed
            cd web && npx tsc --noEmit  → 只剩 2 条既有错，本卡零新增
            node tools/check_design_constraints.mjs web → 11 条规则 0 违规
            python tools/check_line_endings.py → 行尾一致：195 个文件全是 LF
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① 建尺子、混入 CRLF 判红并指出文件 | `test_a_crlf_file_is_reported_with_its_name`、`test_a_mixed_file_is_reported_as_its_own_kind`、`test_an_all_lf_file_passes`（正例）、`test_classify_tells_the_three_shapes_apart`、`test_the_scanned_face_is_not_empty`（扫描面为空**不是「干净」**）、`test_the_scanned_face_is_where_the_strippers_actually_look` |
| ② 根因写进判据、构造 CRLF 文件断言剥注释失效被检出 | `test_the_js_stripper_really_fails_on_crlf`——**真去跑 `node`**，让它自己证明「同一份剥刀，LF 下剥掉 1 处、CRLF 下剥掉 0 处」。只在 Python 里描述根因等于把「JS 正则怎么理解 `\r`」当成共识 |
| ③ 接进全局门 + `.gitattributes` 评估 | `test_this_gate_runs_inside_pytest_q`（问 pytest 的收集面，不读源码找 `skipif`——`WIRE-05` 那次实测读源码会判到自己的断言串上）、`test_the_cli_runs_and_says_something_useful`、`test_the_git_attributes_question_is_answered_not_skipped` |
| ④ 关闭问题单 | `test_the_ticket_is_closed` |

**`.gitattributes` 的结论（卡面要求「NEVER 悄悄略过」）**：
**本仓不是 git 仓库**（`git rev-parse --is-inside-work-tree` 不通），
`.gitattributes` 无处生效，故不加。这个结论由判据钉住——
**哪天本仓变成 git 仓库，那条会红**并提醒去加 `* text=auto eol=lf`
（否则 checkout 会把行尾又翻回 CRLF，这把尺子每次都红）。

**② 改既有文件 35 处**：

| 文件 | 改前 → 改后 | 为什么非改不可 |
|---|---|---|
| `web/` 下 35 个 `.ts`/`.tsx` | 行尾 CRLF → LF（**内容逐字未变**，改前有断言核对） | 它们正被剥注释的尺子扫着，而剥刀在 CRLF 下**一条注释都剥不掉**（实测 0/13、0/26）。不修的话，本卡建的尺子会一直红，而那些判据会一直瞎 |

新增：`tools/check_line_endings.py` · `tests/v041/test_line_endings.py`（卡上 outputs）。

**③ 变异考 5 咬住 + 假变异对照绿**

| 变异 | 判据 |
|---|---|
| ① 不报 CRLF（只报 mixed） | 红 |
| ② 不报 mixed（只报 CRLF） | 红 |
| ③ 扫描面缩成空 | 红 |
| ④ 报了却不说后果（detail 换成一句空话） | 红——**第一次改错了位置**，见下 |
| ⑤ 有文件退回 CRLF | 红 |
| ⑥ 假变异对照：只改一句注释 | 全绿 |

**④ 第一次「没红」不是判据的问题，是我改错了地方**：
「剥不掉」这三个字在文件里出现两次——模块 docstring 第 15 行与 `Finding` 的
detail 第 112 行。脚本按第一处命中去改，改的是 docstring，**判据当然不该红**。
按行号定位到 detail 那处后当场咬住。

**这类假阴性比假阳性更危险**：它会让人以为判据是空的，然后去「加强」一条
本来就好好的判据。所以变异考的每一次「没红」都要先查是不是变异本身没生效。

**④** 装载约 8k tokens；**⑤** 禁用词六词 0 命中。

## 6. 登记未做

1. **Python 侧的 531 个 CRLF 文件没动**。Python 的 `re.sub(r"//.*$", "", line)`
   在 CRLF 下**不受影响**（`$` 可以匹配到末尾换行前），这是那张单自己查明的。
   所以它们不在扫描面内——**但两侧行为不一致这件事本身仍在**，
   哪天有人把某把 Python 尺子改写成 JS，会再撞一次。
2. **`web/` 之外的 ts/tsx 没有**（本仓只有 `web/` 一个前端工程根，`DEC-026`）。
   哪天多一个前端根，`SCANNED_FACES` 要跟着加——它是硬编码的一行，
   而 `test_the_scanned_face_is_where_the_strippers_actually_look` 判等值，
   加的时候会被拦下来确认。
3. **没有防止行尾再次被改坏的机制**（非 git 仓库，没有 hook 也没有 `.gitattributes`）。
   目前靠这把尺子在全局门里守着——**它是事后发现，不是事前拦截**。
