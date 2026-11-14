# GAUGE-10 · 第二份扫描器同样不剥注释

**卡** `docs/steward/tasks-v041-b4.json#GAUGE-10` · **cycles 1（oneshot）** ·
**self_review = true** → §4 · **owner_review = false** · **依赖** 无

## 1. 装载清单

卡面 GAUGE-10 · `docs/blocked/SCANNERS-DO-NOT-STRIP-COMMENTS.md` ·
`tools/check_fe_api_contract.py#frontend_calls` 与它的正则 ·
`tools/check_fe_be_parity.py#_without_comments`（第 3 批修好的那一半） ·
`tests/v041/test_fe_api_contract.py` 的 tmp 目录跑法 ·
`docs/blocked/CRLF-BREAKS-COMMENT-STRIPPING.md`。约 11k tokens。

## 2. 扫描器不在卡面写的那个文件里

卡面（照抄单子）说「`tests/v041/test_fe_api_contract.py` 里另有一份独立扫描器」。
**实际上那个测试只是调用方**，扫描器在 `tools/check_fe_api_contract.py#frontend_calls`。

改在真地方（工具），卡面点名的那个文件里**照旧写判据**（新增两条，§4②）。
这不是扩面：同一处一处修，只是地址与卡面写的不同。

## 3. 剥法与第一把不同，因为要保住行号

`check_fe_be_parity._without_comments` 把注释**整段删掉**——它不报行号，无所谓。
本工具报的是 `file:line`，删掉会让后面每一行左移，尺子于是指向别处，
而**一个指错地方的红比不报更糟**：人会去改一段本来对的代码。

所以 `_blank_comments` 把注释字符换成**等长空白**、换行原样留着，偏移量逐字节不变。
它还带一个引号状态机——`"http://x"` 里的 `//` 不是注释起点。

**改前实测**（一句注释 + 一处真调用）：

```
line   5  GET   /account                  ← 唯一的真调用
line   1  GET   /projects/{}/proposal     ← 注释
line   1  GET   /projects/{}/report       ← 注释
line   2  GET   /projects/{}/{}           ← 注释
line   3  GET   /billing                  ← 块注释
```

**改后**：只剩 `line 5 GET /account`，行号仍是 5。

## 4. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_scanner_strips_comments.py -q → 10 passed
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: 301 source files
            pytest -q               → 4078 passed（FIX-06 收卡时 4066，本卡 +12）
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① 第二份扫描器补上剥注释 | `test_the_contract_scanner_no_longer_reads_a_comment_as_a_call` + `test_fe_api_contract.py::test_a_comment_that_mentions_a_path_is_not_read_as_a_call`（**在卡面点名的那个文件里，用它自己的 CLI 跑法**） |
| ② 根因写进判据 | `test_both_scanners_stopped_claiming_that_strings_exclude_comments`（两份说明都要写「反引号」——光说「剥了注释」，下一个人不知道**为什么**要剥） |
| ③ 阴性对照：注释不算调用、真调用仍被抓 | `test_the_real_call_is_still_found_by_both`、`test_stripping_comments_did_not_swallow_the_real_call`；两把尺子**分别验**（只验一把的话，另一把哪天退回去没人知道） |
| ④ 关闭单子 | `test_the_ticket_is_closed`；单子正文写明修在真地方、剥法为何不同、兄弟单为何没一并关 |

**② 改既有文件三处**：

| 文件 | 改前 → 改后 | 为什么非改不可 |
|---|---|---|
| `tools/check_fe_api_contract.py` | 加 `_blank_comments` 并接进 `frontend_calls`；模块说明加根因段 | **卡的正题**；地址与卡面写的不同，见 §2 |
| `tests/v041/test_fe_api_contract.py` | 加两条判据（注释不算调用 / 真调用仍被抓） | **卡上 outputs**，用该文件既有的 `--frontend <tmp>` 跑法 |
| `tests/v041/test_scanner_strips_comments.py` | 新建（卡上 outputs） | — |

`contracts/` · `flint/domain/` · `requirements.lock` · `assets/heldout_questions.yaml`
一字未动；`flint/` 一行未改；未新增依赖。

**③ 变异考：两条活下来了，判据补完才咬住**

| 变异 | 第一轮 | 补判据后 |
|---|---|---|
| ① 不剥注释（退回缺陷态） | 红 | — |
| ② 剥过头（整个文件当注释） | 红 7 条 | — |
| ③ 块注释里的换行也换成空格 | **绿** | 红（`行号漂了：报 3，实际第 5 行`） |
| ④ 拿掉引号状态机 | **绿** | 红（`真调用被吞了：字符串里的 // 被当成了注释起点`） |
| ⑤ 说明里删掉根因 | 红 | — |
| ⑥ 假变异对照 | 绿 | 绿 |

③④ 活下来是**判据的洞**，不是变异没造成功：

- ③ 我的行号判据用的块注释**只有一行**，吃不吃换行都不影响 → 补一条三行块注释的；
- ④ 我的判据里**没有一条出现过带 `//` 的字符串** → 补一条把 `"http://…"`
  放在同一行真调用**之前**的（不认引号的话，从 `//` 起到行尾全被抹白，
  那次真调用连同它一起消失）。

**④ 变异第一轮有三条根本没造成功**（替换字符串没匹配上），而它们报的是「绿」。
**没造成功的绿与判据不咬的绿，在返回码上一模一样。** 改成先比对文本是否真的变了、
不变就打印「变异没造成功」再跳过，重跑才分得出上面那两类。
**这是本批第三次靠核对红/绿的理由发现假结果**（前两次 `WIRE-12` / `ROUTE-01`）。

**⑤ 我自己被 heredoc 绊了两次**：往测试里写 `\n` 时，heredoc 把它变成了**真换行**，
文件当场语法坏掉。第二次改用 `chr(92) + "n"` 绕开。
**教训与 `WIRE-11` / `WIRE-12` 同族**：脚本改文件 MUST 先 `ast.parse` 再跑测试，
且 NEVER 在 heredoc 里写反斜杠转义。

**⑥** 装载约 11k tokens；**⑦** 禁用词六词 0 命中。

## 5. 「说明与行为不一致」是这一处的真正代价

两把尺子的说明都写着「只在字符串里找，是为了把注释排除在外」——
**那句话对反引号引的路径不成立**。下一个人照说明去查，会去查字符串提取那一段，
而问题在「什么算字符串」。本单因此绊了两次。

所以 acceptance② 要的不只是「改对」，是**把根因写进说明**，
且有判据盯着那句话还在（变异⑤ 删掉根因当场红）。

## 6. 登记未做

1. **兄弟单 `CRLF-BREAKS-COMMENT-STRIPPING` 没一并关**：那是 JS 侧尺子按 `\n`
   剥注释、遇 CRLF 失效，改动面在本卡 outputs 之外。两处是同一件事的两半，
   **NEVER 修了一半就当整件事完了**——本卡有一条判据专门确认那张单还在。
2. **两份剥注释的实现没有合并**：`check_fe_be_parity._without_comments`（删）与
   `check_fe_api_contract._blank_comments`（换空白）职责不同（一个不报行号、
   一个报），合并要先定「统一用哪种」。属整洁范畴。
3. **`web/lib/types.ts` 里那句被绕行改写过的注释没改回来**：它现在是不带反引号的
   写法，能工作但读起来别扭。改回来是一行的事，但那属 `TYPE-04` 的面。
