
# NET-01 · 录制回放守门器（联网只在采集阶段，验证阶段恒回放）

**卡** `tasks-v041-b2.json#NET-01` · **开工** 机器 UTC 2026-08-04T04:20Z

## 1. 装载清单

卡面 NET-01 · `CLAUDE.md#S2-7` 原话 · `tests/conftest.py` · 全仓 `tests/` 与
`harness/` 里 httpx/urlopen 的出现位置（AST 摸底两轮）· `harness/gate1_live.py`
的 `_RecordingTransport` · 工单 §6 的三档上网授权。约 8k tokens。

## 2. 顺序（§4.2）

测试先落盘先跑红（`ModuleNotFoundError: tools.check_no_live_network`）→ 守门器 →
20 passed。连续第三十一张。

## 3. S2-7 此前只是一句话

「CI NEVER 联网；一切外部调用 MUST 走录制回放」——**没有任何东西在查它**。
一行裸 `httpx.Client()` 打真站，本机有网时照样绿，而它会在三处咬人：
CI 无网、被限流、对方改了返回。**这三种红都不是被测代码的问题**。

## 4. 判据：结构，不是词

| 算违规 | 不算 |
|---|---|
| `Client/AsyncClient(...)` 没有 `transport=` | 用了 `respx`（拦整层传输） |
| `urlopen(` / `requests.<verb>(` / `aiohttp.ClientSession(` | 文件里 http 字面量**全是本机**（§6：本机不算外网） |
| | 白名单里的**采集脚本**（逐条列名 + 理由，只给 `harness/`） |

**「只要有一个外部 URL 字面量，本机豁免就不成立」**：半本机半外网的文件最危险——
跑起来一半是回放、一半在真打。

## 5. 反向断言逼出两处真东西

`test_every_whitelisted_collector_really_has_a_live_hit`（BL-03 同款：名单里每条
今天都必须真有命中）当场逼出两件事：

**① 本机豁免太宽——客户端会「逃逸」。**
`harness/demo_server.py` 文件里**只有 localhost 字面量**，于是被本机豁免整个放过；
而它 `GithubArxivSearcher(httpx.Client(...))` 交出去的那个客户端**在真打
github/arxiv**。补 `_escaping_clients`：被当作**实参交出去**的客户端不享本机豁免——
它去打哪个站由收下它的那一方决定，本文件的 URL 字面量说明不了任何事。

补之前 `demo_server.py` 的白名单条目是**死的**（豁免了一个根本没被判红的文件）；
补之后它有 5 处命中。

**② 一条白名单条目本来就不该有。**
`harness/gate1_live.py` 自带 `_RecordingTransport`——**边跑边录**，本来就走
`transport=`，判据认得出。删掉该条，并在代码注释里写明为什么它不需要豁免。

## 6. 全仓实跑（acceptance③）

```
扫描 379 个 .py 文件（tests, harness）
白名单内（采集面，允许联网）7 处：
    · harness/demo_server.py:111 / :114 / :138 / :186 / :216
    · harness/prod_caliber.py:181
    · harness/run_worker.py:68
验证面没有无护栏的真实外部请求。
EXIT=0
```

**验证面 0 处**——`tests/` 379 个文件里没有一处无护栏的真实外部请求。
采集面 7 处，全部逐条列名并写明理由。

## 7. 变异考：九个全红

| 变异 | 抽掉什么 | 结果 |
|---|---|---|
| ① 裸客户端判据关掉 | 正题 | **8 failed** ✓ |
| ② `transport=` 也算违规（误伤） | 不误伤 | **4 failed** ✓ |
| ③ `respx` 豁免去掉 | 不误伤 | **3 failed** ✓ |
| ④ 本机豁免放宽成「有本机字面量就算」 | §4 的「全是」 | **1 failed** ✓ |
| ⑤ 逃逸规则去掉 | §5-① | **2 failed** ✓ |
| ⑥ 豁免直接丢弃（不进 `exempted`） | 藏起来没人知道 | **2 failed** ✓ |
| ⑦ `urlopen` 不算 | 出网口不止 httpx | **1 failed** ✓ |
| ⑧ 读不了的当成没命中 | 扫描面完整性 | **1 failed** ✓ |
| ⑨ 只扫 tests 不扫 harness | 白名单机制的前提 | **2 failed** ✓ |

九次变异后 `tools/check_no_live_network.py` 的 sha256 与变异前逐位相同。

## 8. verify 与 self_review

```
verify_cmd: pytest tests/v041/test_network_discipline.py -q → 20 passed
python tools/check_no_live_network.py → 379 文件，验证面 0 处，EXIT=0
ruff check . --no-cache → All checks passed!
```

**① acceptance 映射**

| acceptance | 测试 |
|---|---|
| ① 扫测试面，无护栏的真实外部请求即红并点名行号 | `test_a_bare_httpx_client_is_flagged`、`test_a_bare_async_client_is_flagged_too`、`test_other_live_paths_are_flagged`（2 例）、`test_the_finding_names_the_file_and_line`、`test_the_repository_has_no_unguarded_live_network_today` |
| ② 采集脚本走白名单豁免并逐条列名，边界写死 | `test_the_whitelist_names_collectors_one_by_one_with_reasons`、`test_the_whitelist_never_covers_a_test_file`、`test_every_whitelisted_collector_really_has_a_live_hit`（反向）、`test_a_whitelisted_hit_is_reported_separately_not_hidden`、`test_both_roots_are_scanned` |
| ③ 阴性对照 + 全仓实跑写进 trace | `test_the_cli_exits_one_and_names_the_offender`（造裸 httpx 测试文件）、`test_the_cli_exits_zero_on_a_clean_tree`、`test_a_broken_file_is_reported_not_counted_as_clean`；实跑见 §6 |

不误伤那一组（acceptance③ 的另一半）：`test_a_mock_transport_is_not_a_violation`、
`test_an_asgi_transport_is_not_a_violation`、`test_a_respx_module_is_not_a_violation`、
`test_a_localhost_only_module_is_not_a_violation`、
`test_one_external_url_makes_the_whole_module_suspect`、
`test_a_client_handed_to_someone_else_loses_the_local_exemption`。

**② 无冻结件偏离**：`contracts/`、`flint/domain/` 未触碰；零新增依赖；
**未改任何既有文件**（只新增守门器与测试）。

**③ 禁用词**：两个产物文件六词 0 命中、本 trace 收尾「等」0 命中。

**④ 复用**：白名单可注入 + 反向断言（名单无死条目）复用 BL-09 / BL-03；
「读不了要报出来」复用 FB-11 的 `unbuildable_apps`；AST 判据不必剥注释的收益同 BL-09。

**⑤ 装载预算**：约 8k tokens。

## 9. 登记未做

1. **没接进全局门**：`verify_cmd` 只跑测试文件。把 CLI 加进合并门是零成本
   （今天 EXIT=0），但那是工程决定，属另一张卡。
2. **只看构造点，不追踪变量**：`c = httpx.Client(); f(c)` 这种先赋值再交出去的写法，
   逃逸规则看不见（只认直接作实参的那种）。真实代码里没有这一形，如实登记。
3. **不查 subprocess 出网**：`curl` / `git clone` 这类走子进程的外部访问不在判据里。
4. **`fixtures/` 录制的完整性不查**：本卡守的是「验证面不联网」，
   「录下来的东西对不对」是另一件事（NET-02 的面）。
