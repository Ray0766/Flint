# PAY-03 · 支付四条安全边界的可执行断言

**卡** `docs/steward/tasks-v041-b2.json#PAY-03` · **cycles 1** ·
**self_review = true** → §6 · **owner_review = true** → §7
**依赖** PAY-02（verified）

## 1. 装载清单

卡面 PAY-03 · `DECISIONS-v04.md#DEC-024`（四条边界原文）·
`tools/no_scaffold_on_screen.mjs` 的头注（命中组/不误伤组的写法）·
`tests/v041/test_doc_gates.py` 的头注（GAUGE-01「把尺子接进门」的做法）·
`flint/billing/meter.py` 与 `ledger.py`（幂等键与账本）。约 9k tokens，预算 40k 以内。

## 2. 四条边界，三条静态一条动态

| # | 边界 | 谁守 |
|---|---|---|
| ① | 零支付密钥 | `tools/check_payment_safety.py`（`payment_secret` 规则） |
| ② | 回调 MUST 验签 | 同上（`unverified_callback` 规则） |
| ③ | 扣费 MUST 带幂等键，重放只扣一次 | **真账本用例**，不是扫描器 |
| ④ | 零卡号字段 | 扫描器（`card_field` 规则） |

**③ 为什么不在扫描器里**：「带幂等键」不是静态形态——代码里有 `event_id` 这个词，
与「重放真的扣不了第二次」是两件事。所以那条打在真跑一遍重放的用例上
（构造 → 落账 → 再落一次 → 断 `LedgerImmutable` → 账上仍只有一条、金额不翻倍）。
这一点写进了扫描器的 docstring，免得有人以为那把尺子管四条。

## 3. 三条不误伤的地方

一把会误伤正常代码的尺子会被立刻关掉，那时四条边界一条都不剩。所以：

1. **从环境变量读密钥是正解**，放行——判据只看**赋给变量的真值形态**
   （右边必须是 ≥16 字符的字面量），`os.environ[...]` 不是字面量；
2. **注释与占位不算**：注释按行剥掉（与 FB-10 同一条口径「判据落在代码上，
   不落在解释代码的话上」），`<your-...-here>` 一类占位符显式放行；
3. **只有看起来是支付回调的函数**才被验签规则管：见函数就要验签的话整棵树都会红。

验签的判定只看**这个函数体内部**——验签写在同文件别的函数里救不了这一个，
因为那个别处的验签根本没跑到这条路径上。

## 4. 扫 0 个文件报红

路径写错、目录空了、后缀没匹配上——三种情况都长得像「干净」。
F-08 的形态就是「过滤器谁都匹配不上却报绿」，这里正面挡掉：`files == 0` 直接返 1。

## 5. 写这张卡时踩出来的三个真 bug

### 5.1 `--json` 把人读摘要也打进了 stdout

调用方 `json.loads(stdout)` 当场炸在「Extra data」上。
改成 `--json` 时 stdout **只出 JSON**，摘要走 stderr。

### 5.2 判据被自己的 docstring 喂饱（本轮第六次同一形状）

`test_the_tool_is_not_wired_to_any_gateway` 原本扫源码正文里有没有 `os.environ[`，
而扫描器的**模块 docstring** 里恰好写着「`os.environ["FLINT_PAYPAL_SECRET"]` 放行」——
判据红在解释规则的那句话上。改成判 **AST**：走 `Import`/`ImportFrom` 与
`Attribute(attr="environ")`。**解释规则的话与执行规则的代码是两回事。**

### 5.3 相对路径调用时 `rel` 带反斜杠，豁免静默失效（**变异考逼出来的**）

`scan()` 原本写 `path.relative_to(repo) if path.is_relative_to(repo) else str(path)`。
传进来的目标是相对路径（`tools`）时，`rglob` 给的也是相对路径，
而 `Path("tools/x.py").is_relative_to(<绝对仓根>)` 是 **False**——
于是 `rel` 落成 Windows 原样 `tools\x.py`，与 `SELF_EXEMPT` 里的 posix 写法**永远对不上**。

后果：**自豁免与它的判据双双静默失效，而两边看起来都是绿的**。
这个洞是变异考⑬ 逼出来的：把豁免放大成「跳过整棵 tools/」时判据竟然不红，
追下去才发现豁免根本就没生效过。改成统一解析成仓根下的 posix 路径。

## 6. 变异考：十九个，四个先活了下来（三个是样例没触到分支）

| 变异 | 抽掉什么 | 结果 |
|---|---|---|
| ① 密钥规则关掉 | 边界① | **2 failed** ✓ |
| ② 私钥块不算 | 边界① | **1 failed** ✓ |
| ③ 卡号字段规则关掉 | 边界④ | **2 failed** ✓ |
| ④ 回调验签规则关掉 | 边界② | **4 failed** ✓ |
| ⑤ 占位符也当成真密钥（误伤） | 不误伤 | **16 passed** ✗ → 补样例后 **1 failed** ✓ |
| ⑥ 注释里提到也算犯规（误伤） | 不误伤 | **16 passed** ✗ → 补样例后 **1 failed** ✓ |
| ⑦ 见函数就要验签（误伤整棵树） | 不误伤 | **6 failed** ✓ |
| ⑧ 验签写在别处也算数 | §3 末段 | **16 passed** ✗ → 补判后 **1 failed** ✓ |
| ⑨ 扫 0 个文件报干净 | §4 | **1 failed** ✓ |
| ⑩ 命中了也返 0 | 退出码 | **4 failed** ✓ |
| ⑪ 条目不点名文件行号 | 可定位 | **1 failed** ✓ |
| ⑫ 规则名混成一个 | 四条分得开 | **1 failed** ✓ |
| ⑬ 自豁免放大成整棵 tools/ 与 tests/ | 豁免逐文件 | **19 passed** ✗✗ → 见 §5.3 |
| ⑭ `--json` 把摘要打进 stdout | §5.1 | **1 failed** ✓ |
| ⑮ 幂等键每次新造 | 边界③ | **2 failed** ✓ |
| ⑯ 幂等键丢掉 owner（跨租户撞键） | D7 | **1 failed** ✓ |
| ⑰ 幂等键丢掉作业（两笔并一笔） | 边界③ | **1 failed** ✓ |
| ⑱ 扫描器自己 import httpx | 零外联 | **1 failed** ✓ |
| ⑲ 扫描器去读环境变量 | 零读密钥 | **1 failed** ✓ |

**⑤⑥⑧ 是同一种错，而且错在我这边**：三个「不误伤」样例**根本没触到它们要守的那条分支**。

- ⑤ 的占位符 `<your-key-here>` 只有 15 个字符，被密钥规则的「≥16 字符」先挡掉了，
  于是「这是占位符」那一支从来没跑过；
- ⑥ 的注释样例里根本没有形似赋值的东西，剥不剥注释结果一样；
- ⑧ 的违规样例整份文件里都没有 `verify_signature`，把判定放宽到全文也不变。

**一个杀不掉的变异，要先问它是不是真的在变异；而一个「不误伤」样例，
要先问它有没有真的走到那条分支上。** 三条样例都改成够长/够像的形态之后全部报红。

**⑬ 活了两轮**：第一轮补的判据查的是 `SELF_EXEMPT` **这个常量**，
而变异改的是**用它的那一行**——常量没动，判据照绿。
第二轮把探针写进真的 `tools/` 目录（`finally` 删掉，末尾再断言已复原，
与 GAUGE-01「构造用例为什么敢改真文件」同一条口径），才把 §5.3 那个真 bug 挖出来。

十九次变异后两个被改文件与变异前逐字相同（baseline 19 passed）。

## 7. verify、全局门与 owner_review

```
verify_cmd: pytest tests/v041/test_payment_safety.py -q → 19 passed
扫描器实跑:  python tools/check_payment_safety.py flint tools docs
            → 支付安全边界干净（扫了 313 个文件）  exit 0
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: no issues found in 289 source files
            pytest -q               → 3183 passed（PAY-02 收卡时 3164，本卡 +19）
```

**扫描器接进全局门**：本文件用 `subprocess` 起它并断 exit 0，
于是 `pytest -q` 从此覆盖它（GAUGE-01 的做法，**NEVER 建一把不在门里的尺子**）。

**owner_review 三件**：

1. **`SELF_EXEMPT` 是四个具名文件**（扫描器自己、它的判据、支付方案文档、本 trace）——
   它们必然写着这些形态，因为那是规则本身与阴性对照。
   **NEVER 用「跳过 tools/ 与 tests/」这种大刀**，判据把这条钉成等值绊线。
2. **`unverified_callback` 是启发式的**：按函数名里有没有 notify/callback/webhook/ipn
   判「这是不是支付回调」。真接线时若回调函数换了个名字，这条规则会漏。
   规则名与理由写在扫描器 docstring 里，接线时（PAY-02 之后的真接入卡）要复核一次。
3. **本卡不接真实网关**：真实商户密钥启用属事前必审，留卡待 owner 在场。

## 8. 登记未做

1. **扫描面是 `flint` + `tools` + `docs` 三棵树**。`web/` 没进去——
   前端不该有支付密钥，但也没被这把尺子扫过。加进去要先确认它不会误伤
   `node_modules` 之外的正常代码，本卡没做。
2. **日志面没扫**。卡上写的是「仓库/日志/trace 里零支付密钥」，
   `docs/trace/` 在扫描面里，**运行期日志不在**——日志是运行产物，不在仓里。
   真接线时要另配一道运行期的脱敏。
3. **幂等只到「同一笔重放拒绝」**。分布式下的并发双写（两个进程同时算同一笔）
   靠的是账本那把锁，本卡没有构造并发用例。
4. **零真实网关、零密钥**（判据钉着）。
