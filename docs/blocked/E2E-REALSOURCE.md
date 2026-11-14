# E2E-REALSOURCE · 真实源端到端冒烟（留卡不执行，需 owner 在场点一次）

**状态** closed · 2026-08-10 · `CN-06`（`DEC-052` 预授权的那一次端到端录制）

批次：v0.4.1 第 1 批 / ASM-05 的姐妹项。状态：**留卡**（不是失败，是红线内的刻意不做）。

## 现象（不是缺陷，是边界）

`docs/steward/连跑工单-v041-第1批.md#4` 写死：

> **本机不算外网**：postgres（55432）、redis 容器、本机模型可用。**真实 github/arxiv
> 检索属红线**——`ASM-05` 冒烟**只走录制回放或本机模型**。
> 真实源冒烟**留一张卡不执行**：写进 `docs/blocked/E2E-REALSOURCE.md`，说明「需 owner
> 在场点一次」，然后继续下一张卡。

`worker.md` §7 也把「真实网络或 API key 启用」列为四类**事前必审**之一，NEVER 授权给
连跑，仅 owner 本人。

## 已做到什么（录制回放那一半已经绿了）

`tests/v041/test_asm_05_e2e.py` 7 条用例全绿，覆盖：提交 → 入队 → worker 消费 → 组稿
产出 paragraph → 渲染出 markdown，外加导出门禁 409/200 两种用例。LLM 走
`httpx.MockTransport` 录制回放，整条链包在 `respx` 护栏里。

**没做的只有一件事**：`gate1_analysis` 那条支线接真实 github/arxiv 检索
（`flint/evidence/search.py:GithubArxivSearcher`）跑一次。

## 需要 owner 提供什么

一次在场授权 + 确认下列两点：

1. 是否允许本机对 `api.github.com` 与 `export.arxiv.org` 发只读检索请求（无 key、无付费，
   但属「真实网络」，落在事前必审内）；
2. 跑完后录制产物放哪（建议 `fixtures/` 下按既有录制回放机制落盘，供 CI 复用——
   这样这条以后就不必再联网）。

## 绕行现状

`flint/jobs/worker_main.py` 的 `gate1_analysis` handler 在 `gate1_deps` 未注入时抛
`HandlerDepsMissing` 并点名要注入什么，作业随即被记 failed——**不静默、不假跑**。
owner 授权后注入 `build_live_deps(dsn, repo, provider, GithubArxivSearcher(...), now)`
即可，装配点已就位，无需改代码。

---

## CN-01（第 9 批 2026-08-09）：**准备到位了，等一次点头**

`CN-01` 把这张单的中国区那一半做到了「一切就绪、停在门口」。owner 点头之后
**一条命令**就能跑完，不需要再配任何东西：

```
python fixtures/_record_cn_real.py                 # 干跑：说清要做什么，一个请求都不发
python fixtures/_record_cn_real.py --owner-is-here # ← 你在场时才带这个开关
```

干跑现在就能看（已实跑，退出码 2）：

```
CN-01 是红线卡：真实源抓取的首次实跑需 owner 在场点一次。
本次**不发任何请求**。带上 --owner-is-here 才会真的联网。

将要抓：weibo, gtrends（日期 2026-08-09）
  weibo    -> fixtures\weibo6-08-09.json  +  fixtures\weibo6-08-09.provenance.json
  gtrends  -> fixtures\gtrends6-08-09.json  +  fixtures\gtrends6-08-09.provenance.json

合规裁决（照实记录、不阻断）：non_commercial @ 2026-08-04
```

**准备到位的四条逐条对上了**：

| 卡面要求 | 落在哪 |
|---|---|
| 抓取脚本可一条命令跑 | `fixtures/_record_cn_real.py`（住在 `fixtures/` 是沿用 `_generate_*.py` 的既有惯例） |
| 录制路径与 fixtures 命名已定 | 沿用 `E12` 布局 `fixtures/{source}/{yyyy-mm-dd}.json`，**不新发明**——既有回放路径 `build_replay_deps` 直接读得到 |
| 限速与 429/5xx/ParseDrift 三类处置已接 | 复用 `SourceThrottle` 与 `flint/sources/errors.py` 那三个异常，**三类各成一条结果**（合并之后一次限频与一次页面改版在日志里长得一样） |
| 合规状态照实记录 | 原样打印 `legal_policy.OWNER_DECISION`（`RECORD_ONLY`），**NEVER 在脚本里重判一次** |

**开关是命令行上的 `--owner-is-here`，刻意不做成环境变量**：
环境变量会被 `.env`、被 CI 配置、被上一条命令留在 shell 里的值悄悄打开，
而这一次点头必须是当场、显式、看得见的。判据 `test_the_switch_is_an_explicit_flag_not_an_environment_variable` 钉着这一条。

### 点头之后会发生什么

1. 脚本抓 `weibo` + `gtrends`（CN），**抓完必录**：fixture 与出处清单（url / 抓取时刻 /
   内容 sha256）同时落盘；
2. 写一张回执 `docs/cn-01-real-ingest-receipt.json`，**逐源记 outcome**；
3. 再跑一条既有回放命令把当天数据灌进 demo 库（脚本本身**不碰库**——
   录制不可逆、灌库可以重来，合在一起的话灌库失败会让人想「再跑一次」，
   而再跑一次就是再抓一次）；
4. `tests/v041/test_cn_real_ingest.py` 里那两条今天跳过的判据**自动开始判**，
   其中一条扫「全库无 `热搜话题NN` 这类合成词」。

### 抓不到怎么办

**如实缺，NEVER 编词面**：三类失败各自记进回执，广场那一行照 `PLAZA-03`
的既有降级态显示。一个源都没抓到时脚本退非零——**「跑过了」与「跑成了」是两件事**。

### 这张单为什么还是 open

`arxiv` / `github` 那一半（本单原本的范围）**没有做**，本次只准备了中国区两源。
单据保持 open 直到 owner 点过；判据 `test_the_ticket_still_says_it_needs_the_owner_in_person`
钉着它——先关掉的话，「等一次点头」这件事就从盘上消失了，而脚本仍然拒跑，
下一个人会以为脚本坏了。

---

## 关闭（`CN-06`）

`DEC-052` 预授权的那一次端到端真实录制**跑成了**，四源全部 `ok`：
`weibo`（访客握手三跳）· `gtrends`（`geo=HK`）· `ghtrend` · `arxiv`。
回执 `docs/cn-01-real-ingest-receipt.json` 记着 `authorized_by: DEC-052`——
**用的是说真话的旗标，NEVER 冒用 `--owner-is-here`**（那个旗标的语义是
「owner 此刻在场」，而这一次 owner 不在场）。

灌库之后广场 `http://localhost:3000/plaza`（不带 `?day=`）落在
**2026-08-10**、CN 区 **125 张卡**，词面是真的
（`马嘉祺严浩翔男人和男孩的区别` 等来自微博真榜，`馬國明` 来自港区 gtrends），
`热搜话题NN` 那批合成词面**一个都没有**。截图在 `.ui-probe/cn06-plaza.png`。

`K1-02` 照旧 open——四源**契约**齐了，而那张单的根因（拿不到数据源令牌）没有消失。

