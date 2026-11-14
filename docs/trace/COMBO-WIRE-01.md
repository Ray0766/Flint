# COMBO-WIRE-01 · 把 combo 的 provider 插上

**第 16 批（停机前收尾）第一张卡。** 1 cycle。

## 一、装载清单（实际读了什么）

| 来源 | 为什么 |
|---|---|
| `docs/steward/tasks-v041-b16.json` | 本批三卡与 rules（`no_new_fronts` 是最硬的一条） |
| `worker.md` | 上岗序列、并行纪律、跑测试的固定前提 |
| `docs/progress-v041.jsonl` 末 20 行 | 定位：第 15 批 `SHIP-15` verified 收工，无在跑卡 |
| `docs/blocked/COMBO-FAMILY-HAS-NO-PROVIDER-ANYWHERE.md` | 卡上 `context_refs`；§五那三行修法 |
| `harness/demo_server.py` · `harness/run_worker.py` · `flint/api/app.py:280-610` · `start-demo.ps1` | 三处实况 |
| `flint/api/combo.py` · `flint/llm/local.py:56-110` | provider 与 model 参数落到哪 |
| `web/app/workbench/page.tsx` · `WorkbenchPreview/Tray/Chat` · `web/app/plaza/page.tsx` · `PlazaCards.tsx` | 探针要打的记号（**只读，一个字没改**） |
| `tests/v041/test_wb_generate.py` · `test_demo_stack_wired.py` · `test_wire_combo.py` | 既有判据的口径与探针缓存机制 |

装载约 34k tokens，未超预算。

## 二、这张卡不是「缺功能」——三处都在盘上

`create_app` 的两个参数（`flint/api/app.py:459`）、
`provider=combo_provider or _UnconfiguredProvider("combo")`（同文件 `:568`）、
以及 `demo_server.py` 自己那句「demo 想让它真跑，把 provider 注进去」的注释——
**缝、说明书、两只已经造好的 `LocalProvider` 全在**，就是没有一个调用方传过它。

## 三、改了什么（逐条：改前 / 改后 / 为什么非改不可）

### ① 新建 `harness/local_model.py`（29 行）

**改前**：`demo_server.py` 与 `run_worker.py` 各写一份同样的三行
（`FLINT_LOCAL_BASE_URL` 默认值 · `FLINT_FREE_TIER_MODEL` 默认值 · `LocalProvider(...)` 五个参数）。
combo 接进来就是**第三份**。

**改后**：地址 / 模型名 / 工厂只在这一个文件里，两个进程都从它取。

**为什么非改不可**：卡面 acceptance 点名要「同一套」。三份默认值一分叉，
「combo 用的是哪个模型」有两个答案，**而两个答案在屏上、在日志里长得一模一样**
——同形先例就在 `demo_server.py` 的 `REDIS_URL` 注释里（API 推 A 队列、worker 守 B 队列，
症状是「作业永远 queued」，与「worker 没起来」分不出来）。

### ② `harness/demo_server.py#build_app`：那一发 `create_app` 补两个参数

```python
app = create_app(DSN, redis_url=REDIS_URL,
                 combo_provider=build_local_provider(), combo_model=MODEL)
```

**缝没拆**：不注 provider 时照旧 503 并点名 combo，阴性对照在
`test_a_family_without_a_provider_still_refuses_and_says_which`（进程内真发一次请求）。
另外把 `:281` 那句已经过期的注释改成实况——**一句变假的注释比没有注释坏**（本文件自己的原话）。

### ③ `flint/api/app.py`：那句 503 不再猜原因

**改前**：`f"{family} 这一族还没有后端（迁移里没有对应的表），本端点未配置。…"`
——通用文案硬套了一个具体原因。**对 combo 是假的**：表全在，缺的是模型。
owner 屏上看到的就是这一句，照它去查迁移的人会白查一趟。

**改后**：默认句不说原因；`FamilyNotConfigured(family, reason=None)` 多一个可选参数，
**知道的才写**。两处知道：`_UnconfiguredProvider`（缺的确定是 provider）与
`_queue_hook(None)`（缺的确定是队列）。其余十来族维持不猜。

**为什么不一族一族补原因**：`_unconfigured()` 服务十来族，它们缺的东西并不是同一样——
硬套一个具体原因就是把这次的错再犯一遍。

### ④ `harness/run_worker.py`：provider 改从工厂取

参数（超时 600 · 关推理 · 4096）**一个字没改**，只是不再自己造。

### ⑤ `start-demo.ps1`：**零改动**

`:178` 那句「combo/Gate 走免费本地 $Model」今天变成真话了。**核的是链不是那句话**：
脚本把 `$Model` 写进后端进程的 `FLINT_FREE_TIER_MODEL`，而 combo 的模型名正是从那个变量来的
（`test_the_start_script_promise_about_combo_is_backed_by_the_wiring`）。
只断言「那句话在脚本里」没有意义——它此前一直在，而它是假的。

## 四、正向取证（真浏览器 · 真栈 · owner 撞到的那条路）

探针 `tools/ui_probe_combo_wire.py` → `.ui-probe/combo_wire/e2e.json` + 六张截图。

| 步 | 实测 |
|---|---|
| 广场 | 55 张热点卡 · 选 3 → `data-selected-count=3` · 提示 `ready` · 建项键可点 |
| 工作台左栏 | 选 `c-20260810-000/002/003` → **托盘逐字同一批** · 证据卡 3 张 |
| 中栏 | 三态各量一次：没选=禁用 · 选了没写假设=禁用 · 两样齐=可点 |
| **按下去** | `POST /projects/combo` → **200**（22.2 秒，本地 35b 真跑）· `proj-combo7e95663fe4` · 5 条主题 |
| 主题页 | 屏上 5 条 = 端点回的 5 条（**库里查得到**，不是只在响应体里活过） |
| 右栏 | 30 块真 Block，块型 `heading` / `paragraph` / `gap_notice` 全落在冻结件那八枚里 |

**右栏那一份不是本次 combo 的产物**，`e2e.json#doc.note` 里如实写着。
链的后两段仍然断着（分析要真实网络 · `analysis_id` 没有回路），两条各有单。
**NEVER 把「渲染得出真 Block」读成「广场到计划书全通了」。**

## 五、被拒的九发逐条归属（`errors` 与 `refusedCalls` 分两格）

应用报错 **0**。被拒 9 发，全部落在最后那一屏（右栏那份真交付物）：

- 1 × `503 /deliverables/{id}/quality` → `QUALITY-FAMILY-HAS-NO-BACKEND.md`（第 14 批开的，仍 open）
- 8 × `404 /hints/` → `REAL-GAP-NOTICES-HAVE-NO-HINTS-REF.md`（真 `gap_notice` 的 `hints_ref` 是空的，
  于是 URL 拼出来就是 `/hints/`）

判据按 URL 分派，并**回头核那两张单是不是还 open**——哪天做掉了这条会红，红得对。
改前那一版判据写的是 `errors == []`，实测 9 条时才发现它把「端点如实拒绝」
与「应用报错」算成同一件事：只数个数的话，九条长得一模一样。

## 六、`web/` 下零字节改动（数了一遍）

开工**前**拍了 `web/` 的 **277** 个文件指纹（`.ui-probe/combo_wire/web_fingerprint.json`）。
判据逐个比，白名单只有同批 `TAIL-01` 明示要动的两个文件——第三个变了当场红。
指纹是改动**前**拍的：改完再拍就是拿结论当证据。

## 七、装配面之外的一处越界（**如实记**）

探针 `tools/ui_probe_combo_wire.py` 不在卡上 outputs 里（outputs 列的是修法面：
`harness/` · `flint/api/app.py` · `start-demo.ps1` · 判据文件）。
而 acceptance 明写「逐屏截图落 `.ui-probe/`」——取证的产出方得有个落点。
放 `tools/` 是照本仓既有位置（`tools/ui_probe_*.py` 六个同族），
放别处下一个人找不到它。**新增文件、零既有文件改动**，故没有走 `docs/blocked/`。

## 八、自审（`self_review=true`）

1. **测试真实覆盖 acceptance**：
   acceptance② → `test_the_demo_stack_hands_combo_a_real_provider`（在真调用点上装记录器，
   不是扫源码里有没有出现那个词——出现在注释里也算数的话，这条从头到尾就是绿的）
   + `test_combo_and_the_composing_family_read_one_definition_of_the_model`
   + `test_only_one_place_in_the_harness_reads_the_model_environment`（剥注释后判代码层）；
   acceptance③ → `test_the_not_configured_message_no_longer_invents_a_cause`
   + `test_a_caller_that_knows_the_real_reason_can_say_it`
   + `test_no_string_in_the_app_glues_not_configured_to_a_missing_table`（下一次有人再塞就红）；
   acceptance④ → `test_the_start_script_promise_about_combo_is_backed_by_the_wiring`；
   acceptance⑤ → 真栈六步 6 条判据 + 六张截图各一条；
   acceptance⑥ → `test_a_family_without_a_provider_still_refuses_and_says_which`；
   acceptance⑦ → 同 ②；acceptance⑧ → `test_this_card_changed_nothing_under_web`。
2. **无冻结件偏离**：`contracts/` 与 `flint/domain/` 一个字节没动。
   `FamilyNotConfigured` 是 `flint/api/` 自己的异常类，不在冻结面。
3. **无禁用词**：新写的四个文件与改动段落扫过「适当 / 合理 / 必要时 / 大约 / 尽量 / 若干」= 0。
4. **复用断言在位**：provider 走既有 `LocalProvider`；缝走既有 `create_app` 参数；
   探针照既有 `tools/ui_probe_wb_generate.py` 的形状（缓存指纹 + 观察者量 pending）。
5. **装载未超预算**：约 34k / 40k。

## 九、`verify_cmd`

```
PYTHONIOENCODING=utf-8 pytest tests/v041/test_combo_wire.py -q
→ 25 passed（33.15s，含真栈探针一次重拍）
ruff check --no-cache harness flint/api/app.py tools/ui_probe_combo_wire.py tests/v041/test_combo_wire.py → All checks passed
mypy --strict flint → 323 files, no issues
```

## 十、留给下一个人的两条实况

1. **改完 `harness/` 必须重起 `:8000`**：跑着的那个进程握的是改前的码。
   本次实测就是先重起（旧 PID 59248/63260 停掉）再跑探针的；
2. **combo 真跑一次 22~34 秒**（本地 `qwen3.6:35b-a3b`，6 个候选主题）。
   探针等的是「等待记号消失」而不是固定秒数——掐时间量到的是运气。
