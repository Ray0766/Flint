# WIRE-05 · 装配面接进全局门，防止再裂开

**卡** `docs/steward/tasks-v041-b3.json#WIRE-05` · **cycles 1（oneshot）** ·
**self_review = true** → §3 · **owner_review = false**
**依赖** `WIRE-01`（verified）

## 1. 装载清单

卡面 WIRE-05 · `tests/v041/test_fe_be_parity.py` 的装配段 ·
`flint/api/app.py` 的 `UNWIRED_FAMILIES` · `docs/trace/AUDIT-01.md` 的对账口径。
约 6k tokens，预算 40k 以内。

## 2. acceptance① 的字面写法（「大于 0 即红」）**盘上判不了**

`backend_not_assembled` 此刻是 **10**：`analysis` / `compose` / `interventions` /
`combo` 四族挂不上，缺的是 `role_resolver`（判 owner/viewer 的那只手）与模型配置。
凑一个 `lambda: "owner"` 上去就是人人是 owner 的安全洞，owner 尚未答复
（`docs/blocked/WIRE-01-FOUR-FAMILIES-NEED-AUTH-AND-PROVIDER.md`）。

直接判零 → **全局门从今天起恒红**。而**恒红的门与没有门等价**：
人会开始习惯性忽略它，那正是 F-11 那条教训的另一面。

所以门判的是**等值**：**未装配面 == 登记面**。卡面要的效果一条不少：

| 情形 | 结果 |
|---|---|
| **新增模块忘了挂** | 它不在登记面里 → **红**（本卡要抓的那个） |
| 四族接上了 | 登记面该缩 → 红，提醒来改判据并关单 |
| 谁把登记面注水 | 红（变异①实测） |
| 谁把登记面清空 | 红（变异②实测） |

`WIRE-01` trace §8.1 就登记过这条口径，本卡照它落地。

## 3. 阴性对照：真造一次「忘了挂」

等值判据有一种典型的空转方式：**两边都是空集也叫相等**。
所以不能只判等值，要真造一次。

`test_a_new_module_that_forgets_to_mount_turns_this_gate_red` 往
`flint/api/` 放一个临时模块（一条 `GET /plaza/wire05-never-mounted`），
断言它**被报成未装配**且门变红，然后 `finally` 删掉，
再断言删干净了、门恢复绿——**NEVER 留在产品树里**（卡面点名）。

实跑后 `ls flint/api/_wire05*` → 无此文件；全局门 3714 passed。

## 4. 「门里跑得到」这条判据，第一版是假的

卡面 acceptance③ 引 F-11：**不在门里的尺子等于没有**。

第一版写的是「读本文件源码，断言里面没有 `pytestmark` / `skipif`」——
**它判到了自己的断言串上**（那两个词就写在断言里），当场假红。

改成**问 pytest 它到底收没收到**：
`pytest --collect-only -q -k <这条判据的名字>`，断言输出里有
`1/3714 tests collected`——分母是全仓收集面，证明它是在**默认那一跑**里被收到的，
而不是只有指名道姓才跑得到。

这是本批第四次撞上同一类问题：**扫源码字符串 ≠ 判行为**
（前三次：`include_router` 语句、`useScreenData` 标识符、撞车守卫无对照）。

## 5. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_fe_be_parity.py -q → 42 passed
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: 299 source files
            pytest -q               → 3714 passed（WIRE-04 收卡时 3712，本卡 +2 +1 替换）
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① 计数写成硬判据、逐条列出是哪些路由 | `test_no_route_is_unassembled_without_being_registered_first`（判等值；失败信息**分两行**列出「没挂也没登记」与「登记了却已挂上」，读的人直接知道该做哪件事） |
| ② 新增模块忘了挂 → 必须红，临时模块用完即删 | `test_a_new_module_that_forgets_to_mount_turns_this_gate_red` |
| ③ 判据在 `pytest -q` 里跑得到 | `test_this_gate_runs_inside_pytest_q`（问 pytest 的收集面，不是扫源码） |

**② 改既有文件一处**：

| 文件 | 改前 → 改后 | 为什么非改不可 |
|---|---|---|
| `tests/v041/test_fe_be_parity.py` | 删掉 `test_the_exit_criterion_is_a_number_this_tool_can_actually_report`（它断言该计数 **> 0**），换成本卡三条 | 那条是 `DEC-031` 落地时留的**临时判据**，作用是「装配没做完之前别把出口判据写成 0」。装配做完了，它的使命结束——留着反而会在四族接上那天挡住正确的结果。它自己的 docstring 就写着「装配卡做完后来这里改判据」 |

**未改**：`tools/check_fe_be_parity.py`（本卡只加门，不动尺子）。

**③ 变异考 2 咬住 + 假变异对照绿**（另见 §3 的临时模块对照）

| 变异 | 判据 |
|---|---|
| ① 登记面注水（把 `/categories` 写进 UNWIRED） | 红 |
| ② 登记面清空（假装一族都不缺） | 红 |
| ③ 假变异对照：只改一句注释 | 全绿 |

**④** 装载约 6k tokens；**⑤** 禁用词六词 0 命中。

## 6. 登记未做

1. **`WIRE-04` 交接的那条操作纪律没做成判据**：改了 `flint/api/` 或
   `harness/demo_server.py` 之后跑取证前 MUST 重启 `:8000`，否则量到的是旧代码。
   做法可以是「取证报告里记下后端进程启动时间，与最后一次源码 mtime 比」——
   **本卡没做**：那要动 `harness/fe_smoke.py`，超出本卡 outputs（只有测试文件）。
2. **四族接上那天**，`UNWIRED_FAMILIES` 要清空、
   `test_an_unmounted_route_is_reported_as_idle_capacity` 的样本要换，
   本卡的等值判据会因为「登记面该缩」而红——**那正是提醒机制**，不是缺陷。
