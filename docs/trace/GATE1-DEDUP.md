# GATE1-DEDUP · trace

**卡**：一次分析取两遍数（`DEC-057` 那一跑的留痕：28 发 / 13 个不同 URL）。
**结果**：verified · 2 cycles · 判据 14 条全绿 · 往返数 **28 → 14**。
**过程里我把判定改坏过一次，被既有判据当场抓住。**

## 一、先把两处调用各自要什么读清楚（卡面第一条）

| 调用点 | 它要的 | 为什么 |
|---|---|---|
| `retrieve`（`_collect_docs`） | 全部文档**去重后的平铺清单** | 存快照、过 provenance 检查 |
| `judge`（`_judge_payload`） | **每条 query 各自那一份** | refute 命中率按 refute query 取；竞品按 landscape query 逐条抽、数边际新名字 |

**两处要的不一样，而都能从同一份 `docs_by_query` 得到**——平铺清单是它的去重并集。

所以处置是**让两处共享同一批结果**，不是加缓存
（owner 逐字，也是我上一轮的判断）：缓存会把「取了两次」变成「看起来取了一次」，
而两处各自要什么这件事仍然没人说得清。

落点：新增 `_fetch_docs_by_query`（整跑唯一取数处）与 `_flatten_docs`（从映射推平铺清单）；
`_judge_payload` 的 `docs_by_query` 是**必填参数**——给默认值的话，
忘了传的调用点会安静地退回老路。

## 二、我按文本共享，当场把判定改了

第一版 `_fetch_docs_by_query` 按 `query.text` 共享。理由写得很顺：
「`github_search_url` / `arxiv_search_url` 只吃 text，两条同文本的 query
问上游的是同一个问题」。

**跑测试时判定从 `B_red_ocean` 翻成了 `C_opportunity`。**

根因：`Searcher` 是一个**协议**，不是那一个实现。
`flint/jobs/gate1.py#_offline_searcher` 按 `query.intent` 分支——
`landscape` 回竞品清单、其余回论文。按文本共享之后 `support` 先跑并占住那段文本，
随后同文本的 `landscape` 拿到**论文而不是竞品**，竞品数归零。

> 一个「只是少打几发网络」的改动**改变了判定结论**。
> 少打几发是省钱，改判定是产品事故——两者绝不能混在一次改动里。

抓住它的是 `tests/m2/test_m2_040` 与 `test_m2_049`（既有判据，不是我新写的）。

**而我自己那条「前提判据」判错了对象**：我写的是
「两个 URL 构造器只吃 text」——那是**那一个实现**的事实，
不是 `Searcher` 契约的事实。改成钉住「协议允许按 intent 分支」，
它成立，按文本共享就 NEVER 能做。

处置：键改成 `query_id_for(query)`——**对任何 Searcher 实现都安全**。

## 三、剩下那一发是**写下来的**，不是忘掉的

按 query 身份去重之后：**28 → 14 发**，而不同 URL 有 **13** 个。
差的那一发正是 `support` / `landscape` 共享 `brain-computer interface` 那一对。

**没有在本卡解决**：它要在**知道 URL 怎么算出来的那一层**（searcher 自己）解决，
而难点是记忆的作用域——`harness/run_worker.py` 的 `build_deps()` 只造一次 searcher，
实例活整个 worker 生命周期，记在它身上会跨作业跨天复用结果。
把它变成每跑一个新的、或给它一个「这一跑」的句柄，都是**接口改动**。

单据 `docs/blocked/GATE1-SAME-TEXT-TWO-INTENTS.md`，判据钉着「这一发还在且有单据」——
没有它的话，**下一个人会以为已经修干净了**。

## 四、抄本退役：全仓原来有**三份**同样的取数循环

| 落点 | 情况 |
|---|---|
| `flint/jobs/gate1.py#_collect_docs` | 正主 |
| `flint/revalidate/run.py` | **自带一份**——复核那一路也在取两遍 |
| `tests/m3/test_m3_025.py` | **又一份** |

三处都改成走同一对函数。判据 `test_no_call_site_keeps_its_own_copy_of_the_loop`
扫全仓：`flint/` 下 NEVER 再有第二处 `for doc in deps.searcher(`。

> 两处各写一份循环的话，去重口径哪天改了只有一处会跟上。

## 五、续跑路径如实处理

`judge` 可以在**新进程里**接着跑（`if not docs: restore_docs(...)`），
而快照里存的是**平铺去重后的 docs**，没有「哪条 query 出了哪些」这一层映射。

所以那一支重取一次，并写明：**这仍然比改前好**——
改前是每跑一次都取两遍，现在只有「跑到一半断了再续」才会多取一遍。
把映射也存进快照要定它的格式与体积，不在本卡范围。

## 六、认证接缝（owner：本版不配 token）

`GithubArxivSearcher.__init__` 加 `auth_headers`，**今天注入的是空**。
注释里写清三件：

- 那个真实数字（`x-ratelimit-limit: 10`，`DEC-057` 那一跑用掉 4）；
- **配 token 时从这里进，NEVER 在本文件里读 env**——
  模块层读环境变量的话，「这次跑带没带凭据」就不是调用方能决定的事，
  而 CI 与本机会因为一个忘了清的变量跑出两种行为；
- 重启条件（owner 逐字）：**第二个并发用户**，或**一次分析的 github 请求数达到两位数**。
  到那时回来要凭据裁决，**NEVER 自行开通**。

`K1-02` 补记了那个真实数字与本版不配的裁决——
owner 逐字：NEVER 再只写「额度是上游能收紧的」这种话。

## 七、门

五条全绿：`ruff` 通过 · `mypy --strict` 322 文件 ·
`pytest -q` **5280 passed / 0 failed** · `tsc` 退 0 · `vitest` 858 passed。

> 整跑第一轮红过 3 条：`m3_025` 的调用点没跟上（第三份抄本），
> 而 `fe_views` 那两条是**它崩在前面留下的库状态**——根因修掉后自愈。
> 逐条点名而不是按族小结，正是为了看出「三条红只有一个根因」。
