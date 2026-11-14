# WIRE-10 · combo 族一条路由 + 模型地址进配置

**卡** `docs/steward/tasks-v041-b4.json#WIRE-10` · **cycles 2（oneshot=false）** ·
**self_review = true** → §5 · **owner_review = true** → §6 · **依赖** `AUTH-03`

## 1. 装载清单

卡面 WIRE-10 · `flint/config.py` 的 `Settings` / `load_settings` / `REQUIRED_ENV_KEYS` ·
`flint/api/combo.py` 的 `ComboApiDeps` 与端点 · `flint/api/schemas.py#ComboCreateRequest` ·
`flint/embed.py` 的 `DeterministicHashBackend` · `harness/demo_server.py` 的装配段。
约 13k tokens，预算 40k 以内。

## 2. 模型地址从「写死在 demo 源码里」变成一条配置

改前 `Settings` 只有三项，而 combo 要 `provider` 与 `embed_service`——
demo 是从模块级 `OLLAMA` 常量拿的。**那条路 NEVER 进产品**：
一个写死在源码里的模型地址，换环境时没有任何东西会提醒你它没跟着换。

新增 `ModelAccess`（`FLINT_MODEL_BASE_URL` / `FLINT_MODEL_NAME` / `FLINT_EMBED_MODEL`），
三条不肯含糊的地方：

1. **不设就是没配，NEVER 编默认地址**。一个猜出来的地址要么连不上（好），
   要么**连上了某个不该连的东西**（更坏）。判据扫 `flint/config.py` 与
   `flint/api/app.py` 的**代码常量**，一个写死的地址都不许有；
2. **缺一项 NEVER 算半配**（`configured` 要两项齐全）。地址在而模型名空时，
   调用会以一个说不清的错误失败——那种失败读起来像「模型坏了」，真相是「配漏了一项」；
3. **模型项 NEVER 进 `REQUIRED_ENV_KEYS`**。设成必填会让所有不跑模型的部署
   （以及 CI）起不来，而「这套环境不跑模型」是一个正当的状态。

嵌入那一侧不吃模型：`embed_service` 用确定性哈希后端，它不需要配置，
也 NEVER 假装自己是真嵌入（那份后端自己的 docstring 写着这句）。

## 3. `UNWIRED_FAMILIES` 空了——五条判据兑现它们自己写的那句话

四族接完之后，五条等值判据**同时红**，每一条的 docstring 里都预告过这一天：

| 判据 | 它自己写的那句话 |
|---|---|
| `test_each_unwired_family_says_what_is_missing_and_holds_a_ticket` | 「一族都没登记——**若真的全挂上了，把本条改成断言空集**」 |
| `test_an_unmounted_route_is_reported_as_idle_capacity` | 「等四族接上，本条会因为**找不到闲置样本**而红，那正是提醒来这里改判据的机制」 |
| `test_the_demo_stack_adds_exactly_the_families_it_alone_can_wire` | demo 多出来的那几族（三次接通中各红过一次） |
| `test_the_gap_shrank_from_fifty_one_to_ten` | 10 → 7 → 5 → 1 → **0** |
| CLI 那条 `未装配（能力闲置）> 0` | 同上 |

全部翻成断言空集。**这些红不是坏消息，是记账**。

## 4. demo 栈就此与可部署应用只差两条中间件

`WIRE-07~10` 把四族全接进 `create_app` 之后，`harness/demo_server.py`
**一族都不再自己挂**，连装配器都不需要了。它与可部署应用现在的差别只剩：
注 demo 身份的中间件、放开 CORS 的中间件。

撞车守卫的阴性对照因此**换了落点**：改前在 demo 上 monkeypatch
`create_combo_app` 造撞车，现在 demo 没有那个落点了——改成直接对
`_Assembler` 造一次真撞车。**守卫只在真撞车时说话，所以要造一次才量得到它。**

## 5. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_wire_combo.py -q → 13 passed
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: 301 source files
            pytest -q               → 4004 passed（WIRE-09 收卡时 3991，本卡 +13）
对账器:     backend_not_assembled 1 → **0**
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① Settings 加模型接入项 | `test_settings_now_carries_a_model_access_block`、`test_the_model_keys_are_read_from_the_environment`、`test_half_a_configuration_is_not_a_configuration`、`test_the_model_keys_are_not_required_to_boot`、`test_no_default_model_address_is_invented_anywhere` |
| ② 没配时回「未配置」、NEVER 空结果 | `test_an_unconfigured_model_answers_service_unavailable`、`test_the_refusal_carries_no_fabricated_result`（**判形状**：响应体里不许出现 `topics` / `project_id`——带一个空 `topics: []` 回去的话，前端会渲染成「一个都没组合出来」）、`test_the_placeholder_provider_raises_instead_of_answering` |
| ③ 挂上 + 探活 + 登记删掉 | `test_the_combo_path_is_mounted`、`test_the_combo_path_is_not_404`、`test_the_unwired_register_is_finally_empty` |
| ④ NEVER 新增依赖 | `test_no_new_dependency_was_added`、`test_a_configured_provider_replaces_the_placeholder`（**回放 provider**，零真实出网——本卡 NEVER 真调用任何模型） |

**② 改既有文件八处**：

| 文件 | 改前 → 改后 | 为什么非改不可 |
|---|---|---|
| `flint/config.py` | 加 `ModelAccess` 与 `Settings.models`；`load_settings` 读三个新键 | **卡上 outputs** |
| `flint/api/app.py` | 挂 combo；加 `combo_provider` / `combo_model` 两条缝；`UNWIRED_FAMILIES` 清空 | **卡上 outputs** |
| `harness/demo_server.py` | 删掉自己那份 combo 装配；删掉不再需要的装配器 | 不删就是 `RouteConflictError` |
| `tests/v041/` 五个判据文件 | 等值判据全部翻成断言空集（§3） | 它们自己写着「全挂上了就来改我」 |
| `tests/v041/test_demo_stack_wired.py` | 撞车阴性对照换落点（demo → `_Assembler`） | demo 不再有可造撞车的族（§4） |

`contracts/` · `flint/domain/` · `requirements.lock` · `assets/heldout_questions.yaml`
一字未动；**未新增依赖**。

**③ 变异考 5 咬住 + 假变异对照绿**

| 变异 | 判据 |
|---|---|
| ① 不挂 combo | 红 |
| ② 编一个默认模型地址（`base_url = "http://localhost:11434/v1"`） | 红（2 条） |
| ③ 半配也算配（只看 `base_url`） | 红 |
| ④ 模型项进 `REQUIRED_ENV_KEYS` | 红（2 条） |
| ⑤ 登记没跟着删 | 红 |
| ⑥ 假变异对照：末尾加一行注释 | 全绿 |

**④ 判据自己踩坑，本批第四次**：地址扫描第一版扫所有字符串常量，
当场把 `ModelAccess` 的 docstring 判成违规——**那段话里引用
「一个猜出来的 localhost:11434」正是为了禁止它**。
改成跳过 docstring 节点。四次分别在 `AUTH-02` / `AUTH-05` / `WIRE-09` / 本卡。

**⑤** 装载约 13k tokens；**⑥** 禁用词六词 0 命中。

## 6. owner_review

**`FLINT_EMBED_MODEL` 这一项现在没人读。** 加它是因为「嵌入用哪个模型」
迟早要配，但当前 `embed_service` 用的是确定性哈希后端——它不吃模型。

两条路：① 留着（配置面一次到位，接真嵌入时不用再改 `Settings`）；
② 现在删掉，等真接嵌入模型时再加。

**本卡选了①并把这件事写在这里**——一个没人读的配置项，
时间长了会被当成「配了就生效」。你若认为该删，那是一行的事。

## 7. 登记未做

1. **`combo_provider` 没有从 `Settings.models` 自动接过去**。
   `create_app` 收的是一个现成的 provider 对象，谁去读配置、造 provider、
   传进来，是**部署面**的事（`harness/run_worker.py` 那侧已有先例）。
   本卡只把配置项与注入口备齐。
2. **真跑一次 combo 没做**：那要真模型或一份完整录制，属 `E2E` 的面。
3. **`ModelAccess` 没有校验地址形态**（比如必须是 http/https）。
   校验要定「什么算合法」，那是配置口径，不是本卡的。
