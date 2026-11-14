# DESIGN-01 · 工作台①：`design_generate` 没有消费者

> v0.4.1 第 5 批第八张。`depends_on: []`。
> **状态：started，尚未写代码。** 上一轮在卡边界收敛（`worker.md §2.5`）。
> 下面是**已经读过、打过、核过**的底账，下一轮直接用，NEVER 重推一遍。

## 一、卡面那句话逐字属实（已核）

`flint/jobs/dispatch.py:59-62` 的 `UnwiredKindReason` 里逐字写着：

```python
"design_generate": (
    "flint/design/session.py 的 delta_events / replay_window 是同步纯函数，"
    "仓里还没有 design_generate 作业的消费者。"
),
```

同一张表里还有另外两条未接线的（`translate`、`template_solidify`）——
**本卡只动 `design_generate` 那一条**，另外两条留在表里（它们各自的理由仍然成立）。

## 二、接线面在哪（三个文件，形状已看清）

| 位置 | 现状 | 本卡要做什么 |
|---|---|---|
| `flint/jobs/dispatch.py:42` `WIREABLE_KINDS` | 7 个 kind | 加 `"design_generate"` |
| `flint/jobs/dispatch.py:54` `UnwiredKindReason` | 3 条 | 删掉 `design_generate` 那条 |
| `flint/jobs/worker_main.py:237` `build_handlers()` | 7 个 handler | 加 `"design_generate": _design_generate_handler(deps)` |

`build_dispatch_table()` 会校验 **handlers 恰好覆盖 `WIREABLE_KINDS`**
（`dispatch.py:128-136`：少一个是漏接线、多一个是 key 拼错，两边同时改才过）。
卡面 acceptance⑤「移出 `UnwiredKindReason` 后分派表仍覆盖判别联合全部成员
（`IncompleteDispatchTable` 判据不倒）」说的正是这条校验。

**handler 的样板照 `_revalidation_handler`（`worker_main.py:204-219`）**：
`deps.<x>_deps is None` → 抛 `HandlerDepsMissing` 并在消息里写清「需要什么、默认出处在哪」，
NEVER 静默跳过。

## 三、既有可复用件（NEVER 新写）

- `flint/design/session.py`
  - `delta_events(job_id, fragments, *, start_seq, now, ephemeral=False)` → `list[JobEvent]`
    （`payload` 是 `DesignDelta(kind="design_delta", seq, fragment)`；
    **空 fragment 直接 `ValueError`**：一个什么都没带的 delta 只让前端多渲染一次空）；
  - `replay_window(...)` / `fold` / `persisted_events` / `unfolded_ephemeral` / `resume_text`
    —— 断线续跑那一半**已经建好了**，本卡是去调用它们，不是去实现它们；
  - `EphemeralNotCheckpointed` 是它自己的保护：标了 `ephemeral=True` 的事件
    必须被检查点盖住。
- `contracts/protocols.py:100` `LLMProvider`：`generate(prompt, tools)` 与
  `generate_structured(prompt, schema, max_retries)`。**设计产物走哪一个要先定**：
  设计稿是自由文本（流式逐块出），`generate` 更贴；`generate_structured` 是给
  verdict 那类结构化输出的。
- `GET /design/sessions/{job_id}/replay` 端点第 4 批已装配（卡面 acceptance④ 点名）。

## 四、红线（工单 §5 第 7 条，已确认怎么落）

- **运行时用本机免费档模型**；
- **测试恒 fixture 回放**，`respx` 护栏断言零真实出网；
- 本机不算外网（postgres :55432 / redis / 本机模型 / localhost）。

既有护栏在 `tools/check_no_live_network.py` 与各卡的 respx 用法，**照抄既有写法**，
NEVER 自己另起一套 mock。

## 五、下一轮的第一个动作

1. 写失败测试 `tests/v041/test_design_generate_job.py`（先跑红）：
   - 分派表覆盖判别联合全部成员（`IncompleteDispatchTable` 不倒）；
   - `design_generate` 不再出现在 `UnwiredKindReason`；
   - handler 缺依赖时抛 `HandlerDepsMissing` 且消息里写明默认出处；
   - fixture 回放下逐块产出 `design_delta`，seq 连续且不重排；
   - 断线后 `replay_window` 取回已产出的块，**NEVER 从头重跑**；
   - `respx` 护栏：整条链路零真实出网。
2. 再实现到绿。

## 五之二、实际做出来的（本轮完成）

### 落点

| 文件 | 改前 | 改后 |
|---|---|---|
| `flint/jobs/design_generate.py` | 不存在 | `run_design_generate` + `DesignGenerateDeps` + `load_design_session` |
| `flint/jobs/dispatch.py` | `design_generate` 在 `UnwiredKindReason` | 移进 `WIREABLE_KINDS`，另两条留在表里 |
| `flint/jobs/worker_main.py` | 7 个 handler | +`_design_generate_handler` 与 `design_generate_deps` 注入位 |
| `flint/jobs/events.py` | 载荷表 4 种 | +`design_delta`（**不补的话块写得进去、读不回来**） |
| `flint/api/app.py` | `load_session=None` | `_design_session_loader(dsn)`（**超出卡面 outputs，在此登记**） |

### 三处设计判断

**① 收尾标记不能省。** 没有它，「推完了」与「推到一半」在日志里长得一模一样，
「已经收尾就一次模型都不调」那条就只能靠猜文字长度来判——
而本模块拿不到「设计稿应该多长」这个数，猜出来的那个数会在某一天把半份稿子当成全稿。
所以跑完追加一条 `StatusChanged(state="done")`。

**② 续跑时若模型给的稿子与已推出的那段对不上，照实抛。**
悄悄接上去会让用户读到一段前后不接的文字，而屏上没有任何异常信号。

**③ 会话取数件只交出 delta。** 同一个 job 的日志里还有状态事件，
而 `resume_text` 对每一条取 `.payload.fragment`——把状态事件也交出去，那一行当场 AttributeError
（实测被自己的判据抓到）。会话的事件流说的是**设计文字**这一条流。

### 判据（17 条）

分派表移出与覆盖不倒（含阴性对照：少一个 kind 必须抛）· 缺依赖时抛并写清默认出处 ·
逐块出且无空块 · seq 单调且 `payload.seq == event.seq` · 源码层 NEVER 自己数 seq ·
**续跑三条**（已收尾时零模型调用与零新事件 / 半截时从下一块接上且不改写已推出的 /
复用 `replay_window` 与 `delta_events`）· 零 HTTP import + respx 护栏零真实出网 ·
载荷表读得回来 · 会话取数件能回文字 · 没有 delta 时回「没有这个会话」而不是空文本 ·
`app.py` 不再把 loader 钉死成 `None`。

### 一处卡号撞车（**请 owner / steward 裁**）

`DESIGN-01` 在 `tasks-v04.json` 已经属于**另一张卡**（对话面板 + SSE）。
新模块 docstring 首行若写这个号，`check_outputs_declared` 会拿 v0.4 那张卡的 outputs 来判它，
报出一句**假的**「少声明」。绕行：首行不写歧义卡号，正文写明出处与理由
（对账器的房规原话：正文里提到别的卡号是**引用**，不是自述）。
**没有动 `LEGACY_UNDECLARED`**（那张表写死是冻结闭集），
**也没有扩大对账器的读取面**（试过，会翻出三条跨批旧账，不属本卡）。
单据：`docs/blocked/CARD-ID-COLLISION-DESIGN-01.md`。

### 两处既有判据按本卡本意更新

`test_pricebook_scan_wired` 与 `test_revalidation_wired` 各有一条钉着「未接线三条」的名单。
`design_generate` 接上之后**应当**从名单里消失——那正是本卡的 acceptance。
两处改成钉「两条」并写明理由，**名单少一条仍然要有人来解释**。

### verify

```
pytest tests/v041/test_design_generate_job.py -q  → 17 passed
pytest tests/ -q                                  → 4189 passed / 4 failed
                                                    （4 条全是 DEMO-JOB-NOT-OWNED-BY-THE-PROBE-USER 那条 403）
mypy --strict flint                               → 302 files, no issues
ruff check . --no-cache                           → All checks passed
python tools/check_line_endings.py                → 208 个文件全是 LF
```

返工四轮，每轮尺子先红：样例稿太短测不出「逐块」· 测试里 `stream.events = keep` 是**别名**
（第二趟的 append 把断点那条也改掉了，断言绿得毫无意义）· 载荷表不认识 `design_delta` ·
会话取数件把状态事件也交了出去。

### self_review（worker.md §4.6）

① 测试覆盖 acceptance：17 条逐条对五条 acceptance，续跑那三条断的是**副作用**
（模型调用次数、事件增量）而不是最终文字——从头重跑最终文字也一样；
② 无冻结件偏离：`contracts/` 与 `flint/domain/` 一字未动，`design_delta` 从 `contracts_v04` 取；
③ 无禁用词：grep 零命中；
④ 复用断言在位：`delta_events` / `replay_window` 两条源码断言 + seq 由流取号；
⑤ 装载未超预算：≈16k tokens。

## 六、本卡时段内清掉的五条卫生红（不属本卡范围，但由本轮引入，如实记账）

跑 `pytest tests/v041 -q` 时抓到五条**本批前七张卡引入的**红，当场逐条修掉：

1. `test_blocked_sheets_state` —— 本批新立的四张单没写机读状态行（`HYG-01` 的格式）。
   四张全部补 `**状态** open`；
2. `test_demo_stack_wired` —— `PLAZA-04` 新读的 `NEXT_PUBLIC_FLINT_USER_ID`
   在 `start-demo.ps1` 里没设（那把尺子守的正是「前端读了而启动脚本忘了设」）。已补；
3. `test_i18n_keys_defined` —— `DS-03` 新增的 `enum.*` 是第六处动态前缀，
   按那条判据自己写的规矩「多一个前缀就来这里确认候选值全都有定义」登记；
4~5. `test_line_endings` ×2 —— 用 Python 改写文件时默认换行把 17 个 `web/**` 文件写成了 CRLF。
   那把尺子的原话：**CRLF 会让 JS 剥注释的正则在 `
` 前走不下去，
   于是「源码里不该出现 X」的判据在那些文件上全部退化成「全文里不该出现 X」**——
   这是一条会让别的判据集体假绿的红。17 个文件全部归一为 LF。

修完 `pytest tests/v041 -q` → **2331 passed / 4 failed**，
剩下的 4 条全部是 `docs/blocked/DEMO-JOB-NOT-OWNED-BY-THE-PROBE-USER.md` 那条 403，
与本批无关。

## 七、本轮已就绪的上下文（不必重读）

前七张卡的产物与实况见 `docs/trace/DS-0{1,2,3}.md`、`PLAZA-0{1,3,4}.md`；
`PLAZA-02` 因两条后端缺口 blocked（单据在 `docs/blocked/`）。
