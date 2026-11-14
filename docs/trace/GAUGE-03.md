# GAUGE-03 · F-05 修复：GRAPH-06 真竞态 + 通用元测试件「抽掉机制后必红」

**卡** `docs/steward/tasks-v041-b2.json#GAUGE-03` · **批次** v0.4.1 第 2 批 · **worker 会话** 2026-08-03T21:42Z 起

## 1. 装载清单（inputs 来源）

| 装载物 | 来源 | 用途 |
|---|---|---|
| `worker.md` 全文 | 仓库根 | 执行纪律 |
| 卡面 GAUGE-03 | `docs/steward/tasks-v041-b2.json` | acceptance / outputs / verify_cmd |
| `docs/review/终检-v04.md#F-05` 全节 + B1 段 + 通用建议段 | context_refs | 缺陷判词与复现数据 |
| `flint/graph/roles.py` 全文（95 行） | inputs | 被测真件 |
| `flint/graph/store.py` 全文（95 行） | 追加 | `GraphStore.nodes()` 的返回语义（代理方案的前提） |
| `tests/v04/graph/test_primary_unique_runtime.py` 全文（160 行） | inputs | 旧用例的压力形态 |
| `contracts_v04/models_v04.py#GraphNode`（12 行） | 追加 | 确认 `primary` 字段可变 |
| `pyproject.toml` / `tests/conftest.py` | 追加 | pytest 配置与「本卡不需要 PG」的依据 |
| `docs/progress-v041.jsonl` 末 20 行 | S8 | 断点定位 |

装载约 22k tokens，未超 40k 预算（S6）。**未**整本装载 PDD、技术方案、WORKORDER。

## 2. 口径收窄：服务端 → 单进程（acceptance④）

GRAPH-06 卡面 acceptance② 原话：「**服务端**并发双写下 primary ≤1 仍成立」。本卡把它收窄为
**单进程并发**，理由逐条回源核过：

1. `migrations/` 全目录 grep `graph_nodes` **零命中** —— `roles.py` docstring 说的 SQL 等价物
   （部分唯一索引 `UNIQUE (graph_id) WHERE primary`）没有落点；
2. `flint/graph/roles.py` 全仓**无生产调用方**（只有它自己的测试 import 它）；
3. `GraphStore` docstring 自述「内存实现；SQL 实现随 E2 的 graph_nodes / graph_edges 两表接入」；
4. `threading.Lock` 是**进程内**的，uvicorn 多 worker 进程下它一开始就不构成保证。

→ 那三个字后面目前没有服务端。本卡产物只声称「单进程并发写下 I12-1 成立」，
跨进程那一半留给 E2 建表那张卡（部分唯一索引）。这一条写进了
`tests/v041/test_asm_graph_race.py` 的模块 docstring，NEVER 只留在 trace 里。

**NEVER 做的事**：没有去改 GRAPH-06 卡面或它的 acceptance 文本（v0.4 已封版，DEC-021/§9.2），
收窄只发生在 v0.4.1 新增的这份测试的自述里。

## 3. 三条断言的分工（本卡的核心设计）

终检对旧用例的判词是「**探针的强度不等于断言的强度**」「两者是不同的命题，别用前者交后者的差」。
所以新用例把三个命题拆开，各自单独证明：

| 断言 | 证明什么 | 为什么不能被别的替代 |
|---|---|---|
| `test_the_storm_puts_more_than_one_writer_inside_the_critical_section` | **压力真的把写入方送进了同一段临界区**（计数闸量出 peak ≥2） | 终检对旧压力做同一测量得到 `max_inside=1`：并发双写从未发生过 |
| `test_the_lock_is_what_collapses_that_overlap_to_one` | 同一份压力、闸包住真锁 → peak 掉回 1 | 少了它，上一条可以被「压力太弱」解释掉 |
| `test_no_reader_holding_the_lock_ever_sees_two_primaries` | **互斥成立**：取同一把锁的读者恒看不到两个主 | 它量的不是「线程撞上过」，撞上由第一条证明 |

第三条是交给元测试件去咬的那条：抽掉 `_lock_for` 之后它必红——**这正是旧那条做不到的**
（终检把旧那条换成 nullcontext 打了 25 次，25 次全绿）。

### 3.1 撕裂窗口为什么不能压在 `_storm` 上（一次实测把首版方案打回）

首版把「必红」压在四写入方互抢上。**跑出来是绿的**（`probe` 报 `survivors=[...]`，即抽掉锁之后
那条断言活了下来）。当场量了一次分布才看清根因：

```
第一次实测（同一份压力，单独跑）：samples=63 max=3 dist={1:32, 2:19, 3:11, 0:1}
pytest 全文件跑时的那一次：       max<=1 —— 一次撕裂都没出现
```

四个写入方按列表序逐格互相清主，某一格上「谁最后写」由线程唤醒次序决定；
owner 自己的节点被别人在几微秒内清掉，撕裂窗口就不存在。**同一份压力有时出现、有时不出现**。
把元测试的「必红」压在这种窗口上，这条元测试自己就是下一个 F-05。

改法：追加 `_lone_handover` —— 老主坐列表最后一格、新主在第一格，写循环按列表序逐个写，
于是「立了新主、还没走到老主那一格」这段窗口**恒等于 4 次停顿（20 毫秒）**，与调度无关。
观察线程全程在跑，它与写入方之间的互斥正是这条要量的东西。`_storm` 保留（真并发压力），
但红的保证来自 `_lone_handover`——这一点在被测函数的 docstring 里写明，NEVER 让读者以为
保证来自那段随机窗口。

### 3.2 停顿加在哪：测试侧的代理，真件一字未动

`_GatedNode` 代理真节点，写 `primary` 前停 5 毫秒（读不停——观察线程要采得够密），
`_SlowStore.nodes()` 返回代理。**`flint/graph/roles.py` 一个字节都没改**：

```
flint/graph/roles.py sha256 = 18289a1e40dfa938…   （终检 B1 段记录的改前值：18289a1e40dfa938…，逐字节一致）
```

这是刻意的：终检 B1 段记着「本批 B1 起初拟改 `flint/graph/roles.py` 抽锁，被 owner 当场拦下」，
理由是坏实现会永久留在仓库里。抽锁只发生在 monkeypatch 里，跑完就还原（tier ②）。

## 4. 元测试件 `tests/_meta/probe_bites.py`（acceptance②）

对外三样：`Replacement`（替换件描述）、`probe()`（只判不抛，返回 `BiteReport`）、
`assert_bites()`（断言版），外加 `CountingGate`（当 `_lock_for` 用的计数闸，`inner` 可选包真锁）。

**四道检查，缺一道结论就是假的**，每道都有构造反例守着：

| 检查 | 失败信息 | 守它的测试 |
|---|---|---|
| ① 目标存在 | 「…没有属性 …：这个补丁打歪了」 | `test_probe_bites_refuses_a_target_that_does_not_exist` |
| ② 替换**之前**是绿的 | 「这些测试**替换之前就是红的**」 | `test_probe_bites_refuses_a_case_that_was_already_red` |
| ③ 替换**之后**全红 | 「这些测试**替换之后仍然是绿的**」 | `test_probe_bites_goes_red_when_the_replacement_changes_nothing` |
| ④ 替换件**真被调用过** | 「替换件**一次都没被调用**」 | `test_probe_bites_refuses_a_conclusion_built_on_an_uncalled_replacement` |

第 ④ 道来自终检对自己 monkeypatch 的自证（「`_lock_for` 被调用 320 次（期望 8×40=320）→ 生效」）。
构造它需要一个「装得上、走不到、却因为别的原因红」的替换件：`build` 在装载时打标记，
装上去的那个函数本身 NEVER 被调用，被守的用例只看标记 —— 于是 ②③ 都过、④ 不过。
没有这道检查，一次打歪的补丁造成的红会被读成「机制起作用了」。

第 ③ 道的阴性对照最要紧：喂一个**语义等同**的替换件（换壳不换互斥），`assert_bites` 自己必须红。
翻不过去，这件元测试件就只会说「都挺好」，那它就是它自己要防的那种东西
（与 GAUGE-02 里那条阴性对照同一个道理）。

## 5. 旧文件保留（acceptance⑤）

`tests/v04/graph/test_primary_unique_runtime.py` **一字未动、不删**，仍 7 passed。

- 它证明的是「`primary_count` 这把尺子认得出多主」—— 仍然有效，删掉就把这份证据也删了；
- 它**不**证明「线程真撞上过」：`naive_set_primary_unsafe` 只把自己那一个置 True、从不清旧主，
  必然留下 8 个 primary，**串行跑也一样红**。而它的 docstring 自述要挡的恰恰是后者
  （`test_...can_actually_fail:96` 原话「否则上一条的绿可能只是因为线程没撞上」）——**这一句仍不成立**。
- 后一半由本卡 `test_the_storm_...` 接手。`test_the_old_runtime_case_is_kept_intact` 机器守着
  「旧文件还在、两条测试名与那个反例探针都还在」，挡的是将来有人用「删掉它」来修这条缺陷。

## 6. verify 与实测输出

```
verify_cmd: pytest tests/v041/test_asm_graph_race.py -q
9 passed in 2.40s
```

并发用例连跑 15 次（本卡的主题就是「绿得不明不白」，一次绿不算数）：

```
9 passed in 2.41s   ×15   （15/15，最慢 2.44s）
```

这 15 次里每一次都包含 `test_removing_the_lock_makes_the_guarded_case_red`，
即**抽掉 `_lock_for` 之后被守用例红了 15/15**。对照终检对旧用例的同一实验：抽掉之后绿 25/25。

## 7. self_review（§4.6）

**① 测试 ↔ acceptance 逐条映射**

| acceptance | 测试 | 判据 |
|---|---|---|
| ① 计数闸量出临界区并发峰值 ≥2 | `test_the_storm_puts_more_than_one_writer_inside_the_critical_section` | `gate.peak >= 2` + `gate.calls == 8`（替换生效自证）；实测 peak=4 |
| ② `probe_bites` 提供「替换后必红、仍绿即元测试红」的断言 | `probe`/`assert_bites` + 四条构造反例（见 §4 表） | 四道检查各有一条 `pytest.raises` 守着 |
| ③ 用元测试件守住新并发用例：抽掉 `_lock_for` 后必红 | `test_removing_the_lock_makes_the_guarded_case_red` | `report.bit` + 调用次数下界 `1+8+4` |
| ④ 口径收窄为「单进程并发」并记录 | 模块 docstring「口径收窄」节 + 本 trace §2 | 四条回源证据；NEVER 声称守住了服务端 |
| ⑤ 旧用例保留不删 + trace 写明它不证明撞上 | `test_the_old_runtime_case_is_kept_intact` + 本 trace §5 | 旧文件 sha 与 7 passed 均在案 |

无 `assert True`、无只测 happy path：三条正面断言各配一条对照（peak 有「闸调用次数」自证、
互斥有「抽掉即红」、元测试件有四条构造反例）。

**② 无冻结件偏离**

```
python tools/check_frozen_additive.py contracts/models.py contracts_v04/models_v04.py
additive 校验通过：models_v04.py 保留了 models.py 的全部 87 类 / 443 字段 / 1 函数签名 / 31 别名；新增 17 类、13 字段、10 枚举/联合成员   exit=0
python tools/check_frozen_additive.py contracts/protocols.py contracts_v04/protocols_v04.py
additive 校验通过：protocols_v04.py 保留了 protocols.py 的全部 24 类 / 1 字段 / 40 函数签名 / 0 别名；新增 0 类、0 字段、0 枚举/联合成员   exit=0
```

本卡未新增任何契约面：只用了既有的 `GraphNode`。`contracts/`、`flint/domain/`、
`requirements.lock`、`assets/heldout_questions.yaml` 一字未动。

**③ 禁用词**

```
扫描 tests/_meta/probe_bites.py + tests/v041/test_asm_graph_race.py：
六词（适当/合理/必要时/大约/尽量/若干）0 命中
收尾「等」1 命中 → probe_bites.py:12「并发 / 竞态 / 幂等 / 加锁 / 事务」
```

那一处是**逐字引用**终检通用建议里的术语「幂等」，不是列表尾的省略词。保留原文，
改字会让引文与被引文本对不上。

**④ 复用断言**：本卡不命中 H1~H8 复用清单（元测试件是新机制，仓库里此前没有同类件；
`CountingGate` 也没有可复用的既有实现）。已复用的是既有真件本身：`roles.set_node_role`、
`roles.primary_count`、`roles._lock_for`、`GraphStore`/`add_node`、`contracts_v04.GraphNode`
——测试侧 NEVER 另写一份图存储或角色规则。

**⑤ 装载预算**：约 22k tokens，未超 40k。

## 7.1 顺序纪律如实记（§4.2）

`tests/v041/test_asm_graph_race.py` 先落盘、`tests/_meta/probe_bites.py` 后落盘（顺序对），
但**两个文件都写完才第一次跑 pytest**，没有在中间跑一次确认「只有测试、没有实现」时的红。
偏离的是「跑一次确认红」这一步，不是「先写测试」。

补偿证据：首跑并非全绿，而是 `1 failed, 8 passed`，红的正是本卡的核心断言
`test_removing_the_lock_makes_the_guarded_case_red`，失败信息由元测试件自己给出
（「替换之后仍然是绿的」）——红→改压力设计→绿的完整过程在 §3.1 有实测数据。
下一张卡恢复「写完测试先跑一次」的顺序。

## 8. 顺手修的既有文件（本批 §4.1 要求逐处交代）

**`docs/progress-v041.jsonl`**（append-only，只追加、历史行一字未改）

- **改前**：`DEC-022-029-LANDING` 只有一行 `verified`（2026-08-03T21:23:12Z），没有 `started`。
  于是 `tests/v041/test_ledger_pairing_v041.py::test_v041_ledger_has_no_unpaired_event` 恒红：
  ```
  AssertionError: docs/progress-v041.jsonl 里有未配对事件：[('DEC-022-029-LANDING', 'verified')]
  1 failed, 10 passed
  ```
  即**全局门 `pytest -q` 在本卡开工前就是红的**，与 GAUGE-03 无关，是上一会话漏拍。
- **改后**：追加一行 `{"task_id": "DEC-022-029-LANDING", "event": "started"}`，note 里写明这是补配对行。
- **为什么非改不可**：① 全局门带病，本卡的绿会被它盖住，后续每张卡都要在这条红里作业；
  ② 修法用的是台账自己认的规则——`eval/ledger_pairing.py` docstring 写的是
  **存在性而非位置序**，同一本台账里 `E2E-REALSOURCE` 已有先例（该行 note 原话
  「started recorded after blocked (append-only, existence-not-position…)」）；
  ③ 历史行一个字节没动，补的是「这张卡确实开过工」这个事实本身，落盘时间就是该行 ts。
- 复验：`pytest tests/v041/test_ledger_pairing_v041.py -q` → `11 passed`。

除此之外**零既有文件改动**：本卡产物是两个新文件，`flint/` 下一个字节都没动（sha 见 §3.2）。

## 9. 登记未做（不自行扩面）

1. **跨进程保证**：部分唯一索引 `UNIQUE (graph_id) WHERE primary` 仍不存在，`graph_nodes` 表未建。
   本卡按 acceptance④ 只做单进程口径，NEVER 顺手去建表——那是 E2 的面。
2. **`worker.md` 验收规格未改**：终检建议把「并发/竞态/幂等/加锁/事务类断言 MUST 配元测试」
   写进 `worker.md`。本卡只交了执行件（`probe_bites.py`），改 `worker.md` 属规格面，
   不在本卡 outputs 内，留给 owner/steward 裁决。
3. **仓库里其余并发断言未清点**：`probe_bites` 建好了，但「还有哪些并发断言没配元测试」
   是一次清点，形态与 GAUGE-02 同族，未在本卡 acceptance 内。建议下一批立卡。
4. **F-07 观察项**：`roles.py` 无生产调用方这件事本卡只记录、不接线（接线是候选① ASM 系列的面）。
