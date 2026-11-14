# `POST /projects/combo` 在任何部署上都是 503：`combo_provider` 这条缝全仓没有调用方

**状态** closed · 2026-08-12 · `COMBO-WIRE-01`（开单人 `WB-03`）

**阻断**，且**改动面在本卡 outputs 之外**（要动的是 `harness/demo_server.py`），
按本批 `touch_boundary`「改动面大于卡上 outputs → 停下走 docs/blocked/」开单，
NEVER 自己动手。

## 一、实测（2026-08-12，真栈 :8000，本机 Ollama 在跑）

```
POST /projects/combo
  {"card_ids":["card-20260810-c-20260810-000","card-20260810-c-20260810-001"],
   "hypothesis":"…"}                                     # 两张都是真库里的证据卡

→ HTTP 503（0.1 秒，模型一次都没被调）
  {"code":"FAMILY_NOT_CONFIGURED","family":"combo",
   "message":"combo 这一族还没有后端（迁移里没有对应的表），本端点未配置。这不是故障：没配 ≠ 坏了。"}
```

## 二、根因（源码实查，不是推测）

```
flint/api/app.py:459   def create_app(dsn, redis_url=None, queue_name=None,
                                      aligner_provider=None, combo_provider=None, combo_model=None)
flint/api/app.py:568   provider = combo_provider or _UnconfiguredProvider("combo")   # 一被调用就抛
harness/demo_server.py:264  app = create_app(DSN, redis_url=REDIS_URL)               # 没传 combo_provider
```

`grep -rn "combo_provider" --include=*.py .`（排除 `.venv`）**全仓只有三处**：
签名、`or _UnconfiguredProvider` 那一行、以及 `demo_server.py:281` 那句
「demo 想让它真跑，把 provider 从 `create_app(combo_provider=…)` 注进去」的注释。

**没有任何调用方传过它**——不只是 demo，`WIRE-10` 留的这条缝今天一端都没接。
于是 `/projects/combo` 对**所有**部署都是 503。

## 三、两句过期的话（`stale_premise` 那条规则要求核的，核过了）

1. **503 正文里那句「迁移里没有对应的表」对 combo 是假的**。
   那是 `FamilyNotConfigured.__init__`（`flint/api/app.py:424`）写死的通用括号。
   combo 要的表**全在**（`origins` / `topic_seeds` / `topics` / `projects`，实查在库）；
   缺的是**模型**。照这句去查迁移的人会白查一趟。
2. **`start-demo.ps1:179` 起完后打印「combo/Gate 走免费本地 $Model」**——
   Gate 那半句是真的（`run_worker.py` 注了 `LocalProvider`），
   combo 那半句今天是假的。

## 四、屏上的样子（`CHAIN-04` 那一屏 + 本卡的中栏）

`/combo` 与工作台中栏按下提交，服务端答的就是上面那句 503。
两屏都**原样带出服务端的说明**（`chainClient.read()` 的既有口径：
「前端一句拒绝话都不写」），所以屏上不会转圈、也不会说错——
但用户看到的是「这一族没配」，而他要的是一份计划书。

## 五、修法（我认为是三行，但没动）

`harness/demo_server.py` 已经为 `design_generate` 造好了一个 `LocalProvider`
（同文件第 152 行那一处的同款），把它连同模型名一起传进去即可：

```python
app = create_app(DSN, redis_url=REDIS_URL,
                 combo_provider=<那个 LocalProvider>, combo_model=MODEL)
```

**边界（做的时候 MUST 守）**：
- 只走**免费本地档**（LocalProvider → 本机 Ollama），NEVER 读任何 key（S2-10）；
- 可部署应用那一侧照 `flint/config.py#ModelAccess` 从环境读，
  **NEVER 在 `create_app` 里编一个默认地址**（`app.py:469` 已经写死这条理由：
  猜出来的地址要么连不上，要么连上了不该连的东西）；
- 顺手把 §三那两句过期的话改掉（503 正文那句是通用文案，
  改它会影响所有族 —— 那是另一张卡，不是顺手）。

## 六、需要 owner 的什么

一句「照 §五 接上」即可（本机模型、零网络、零新依赖、零新表）。
接上之后 `/combo` 与工作台中栏的第一步立刻变成真的；
`WB-03-b` 还需要 `docs/blocked/ANALYSIS-ID-HAS-NO-PATH-FROM-AN-ANALYSIS.md`
那一条选定口径才走得完。

## 七、这条为什么今天才被看见

`/combo` 那一屏（`CHAIN-04`）从建好起就没有人在**真栈**上按过那个提交键：
它的判据判的是「按钮在不在、禁用逻辑对不对、拒绝话术从哪来」，
全是不发请求也成立的东西。本卡要把中栏接到这条链上，第一次真按了一下。

## 关闭（`COMBO-WIRE-01` · 2026-08-12）

owner 2026-08-12 的工单原话是「优先做」，边界与 §五逐字一致
（本机模型 · 零网络 · 零新依赖 · 零新表）。落地三处：

1. **provider 插上**：`harness/demo_server.py#build_app` 那一发
   `create_app(DSN, redis_url=REDIS_URL, combo_provider=build_local_provider(),
   combo_model=MODEL)`。缝**没拆**——不注 provider 时照旧 503 并点名 combo
   （阴性对照 `tests/v041/test_combo_wire.py#test_a_family_without_a_provider_still_refuses_and_says_which`）；
2. **模型口径收成一处**：新建 `harness/local_model.py`（地址 / 模型名 / provider 工厂），
   `demo_server` 与 `run_worker` 都从它取。改前那三行在两个文件里各写一份，
   而 combo 接进来就是**第三份**——三份默认值一分叉，「combo 用的是哪个模型」
   就有两个答案，且两个答案在屏上、在日志里长得一模一样；
3. **§三那两句过期的话**：`FamilyNotConfigured` 那句「迁移里没有对应的表」
   改成**不猜原因**（构造方知道真原因时才写 `reason`）；
   `start-demo.ps1:178` 那句「combo/Gate 走免费本地 $Model」核过了——
   判据钉的是那条**链**（脚本把 `$Model` 交给 `FLINT_FREE_TIER_MODEL`，
   combo 的模型名正是从那里来的），不是「那句话还在不在」。

**取证**：`.ui-probe/combo_wire/e2e.json` + 六张截图（真浏览器 · 真栈 · 一步一张）。

**这条链还没到头**（NEVER 读成「广场到计划书全通了」）：本卡接通的是**第一段**。
后两段仍然断着，各有各的单：`ANALYSIS-ID-HAS-NO-PATH-FROM-AN-ANALYSIS.md`（成文要
`analysis_id`，没有回路）与真实网络那条（分析一被消费就打真 github/arxiv，事前必审）。
