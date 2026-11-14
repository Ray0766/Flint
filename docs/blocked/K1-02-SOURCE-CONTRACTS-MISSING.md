# K1-02-SOURCE-CONTRACTS-MISSING · 三条候选源今天写不出解析器（响应契约拿不到）

**状态** open · 2026-08-10 · `CN-05`（四源**契约**已探明；而这张单的根因不止契约，见文末）

**发现者** worker / K1-02 接入时逐条核 · **发现时间** 2026-08-04
**危害** 中 —— 不是缺陷，是**边界**：新源接不进来，九区里除既有四源外没有新增
**改动面** 要么拿到响应契约（需申请开发者账号 / 商务协议），要么真调一次（红线）

## 卡面要什么

K1-02 acceptance①：「新源按既有四源的形态实现（每源一模块 + feature flag + 限速 +
429/5xx/ParseDrift 三类错误）——照 `gtrends.py` 的既有骨架」。

## 逐条为什么写不出来

| 候选 | 请求契约 | **响应契约** | 结论 |
|---|---|---|---|
| `naver_datalab` | **有**（官方示例：`POST https://openapi.naver.com/v1/datalab/search`，`X-Naver-Client-Id`/`Secret` 头 + `keywordGroups` 请求体） | **拿不到**：`developers.naver.com` 的文档页本机取不到（`Claude Code is unable to fetch`），官方示例代码只 echo 响应、不写结构 | 写解析器就得**编**响应结构 |
| `yahoo_jp_realtime` | **没有**：官方页面写明提供排行 API（面向合作方），但无公开端点契约与自助申请入口 | 没有 | 连请求怎么发都不确定 |
| `reddit_data_api` | 有（OAuth） | 有 | **拿不到令牌**：自助注册已关闭、人工审批 2–4 周，且免费档**仅限非商业**，而本产品是商用 MVP |

## 为什么不「先按猜的写一个」

解析器与它的测试会**自洽**——两边都按编出来的形状写，跑起来全绿；
等哪天真连上，它**一行也解析不出来**。而那时它已经被当作「已实现」写进
清单与出口报告里。

本仓一路在防的就是这种自洽（BL-01 的「自洽不等于正确」、GAUGE-03 的「抽掉机制后
必红」都是同一件事）。**宁可没有解析器，也 NEVER 有一个自洽的假解析器。**

## 还有一道更硬的门

四条候选的 `fetch_legal_status` 全是 `unknown`（K2 未决），而 REGION-07 对 `unknown`
**不放行抓取**——也就是说**今天连抓都不该抓**，acceptance③「每源首次抓取录进
fixtures」本身就没有合法的执行路径。

叠加：**真实源首次抓取属红线**（工单 §5：`NET-03` 留卡不执行，需 owner 在场）。

## 要 owner 定的（三选一或另裁）

1. **给 Naver 开发者账号**（自助注册即可拿 Client ID/Secret）：拿到之后
   响应契约可从真实调用取得——但那一次调用属首次真实抓取，**需 owner 在场**；
2. **联系 LINEヤフー 取 Yahoo!リアルタイム检索 的合作方 API 契约**（商务面）；
3. **裁决 Reddit 走不走商用合作**（K1-01 的第 2 问，同一件事）。

在此之前，K1-02 交的是**接入路径**（`flint/sources/candidates.py`）：
种子表 → 合规放行且启用才进表 → 空表按区落 E6 缺数据行。
K2 给出结论那天，改的只是种子表里的两个字段。

---

## 2026-08-10 · 前两源的**真实契约**（`CN-04` 探测实况，`DEC-052` 窗口内）

这张单预言的事发生了：四个适配器全部按合成夹具建，第一次碰真实站点两源全败。
下面是**今天实测**的契约，探测留痕在 `fixtures/_probe/{weibo,gtrends}/`（各带 url /
status / 关键响应头 / body 前 2048 字节 / UTC 时间戳）。

### weibo（探测日 2026-08-09 UTC / 2026-08-10 本机）

| 端点 | 实测 |
|---|---|
| `s.weibo.com/top/summary?cate=realtimehot` | 302 → `passport.weibo.com/visitor/visitor`（新浪访客系统） |
| `s.weibo.com/top/summary` | 同上 |
| `m.weibo.cn/api/container/getIndex?…realtimehot` | 302 → `visitor.passport.weibo.cn/visitor/visitor` |
| `weibo.com/ajax/side/hotSearch` | 403 `{"error":"Forbidden"}` |
| `weibo.com/ajax/statuses/hot_band` | 403 同上 |

**契约结论**：**今天没有一条免登录路**。五发全带浏览器 UA、全跟随重定向。
`CN-01` 报的 302 不是「适配器不跟随重定向」造成的——跟过去落在访客系统页上。
单据 `CN-04-WEIBO-ALL-ANONYMOUS-ROUTES-NEED-A-VISITOR-COOKIE.md` 等 owner 一句话。

### gtrends（同日）

| 端点 | 实测 |
|---|---|
| `trends/api/dailytrends?…`（适配器现在打的） | **404，已下线**——`CN-01` 的判断属实 |
| `trending/rss?geo=CN` | **400** |
| `trends/trendingsearches/daily/rss?geo=CN` | 404 |
| **`trending/rss?geo=US` / `geo=HK` / `geo=TW`** | **200 · `text/xml`** |

**新端点的真实结构**（`geo=US` 那份，逐字）：

```xml
<rss xmlns:ht="https://trends.google.com/trending/rss" version="2.0"><channel>
  <item>
    <title>funeral home</title>
    <ht:approx_traffic>200+</ht:approx_traffic>
    <pubDate>Sun, 9 Aug 2026 08:10:00 -0700</pubDate>
    <ht:picture>…</ht:picture>
```

热度在 `ht:approx_traffic`，形如 `200+`——**是一个区间下界，不是精确值**。
接的时候 NEVER 把 `200+` 读成 `200` 当精确热度用。

**契约结论**：端点活着、结构够用，**而 Google Trends 没有中国大陆区**（`geo=CN` 400）。
这与 `DEC-045`（本版只做中国区）撞上，单据
`CN-04-GTRENDS-HAS-NO-CHINA-REGION.md` 等 owner 定地区口径。

### 这张单继续 open

四源契约还差 `ghtrend` / `arxiv`（归 `CN-05`，本卡 NEVER 顺手碰）。
两源已探明但**都停在 owner 那一句话上**，适配器**一行未改**。

---

## 2026-08-10 续 · weibo **真实契约已探明**（`DEC-053` 授权的访客握手实测走通）

### 握手三跳，全部 200（留痕在 `fixtures/_probe/weibo/`）

| 跳 | 端点 | 实测 |
|---|---|---|
| ① | `POST passport.weibo.com/visitor/genvisitor`（表单 `cb=gen_callback&fp={…}`） | **200** · `{"retcode":20000000,"msg":"succ","data":{"tid":"…"}}` |
| ② | `GET passport.weibo.com/visitor/visitor?a=incarnate&t={tid}&w=2&c=095&cb=cross_domain&from=weibo&_rand=…` | **200** · `succ`，Set-Cookie **`SUB` `SUBP` `SRF` `SRT` `SVB`** |
| ③ | `GET s.weibo.com/top/summary?cate=realtimehot`（带上一步的 cookie） | **200 · 105724 字节 · 52 行 `td-02`** |

**免凭据可行**：全程无用户名密码，`fp` 是一段公开的浏览器环境描述。
端点名不是猜的——`fpPostInterface: "visitor/genvisitor"` 逐字写在
`passport.weibo.com/js/visitor/mini_original.js` 里（已探测留痕）。

### 真实 HTML 与合成夹具的**一处结构差**（适配器今天会在这里抛）

真榜第一行是**置顶行**：

```html
<td class="td-01"><i class="icon-top"></i></td>
<td class="td-02">
    <a href="/weibo?q=%23…%23&Refer=new_time" target="_blank">健全上下贯通执行有力的组织体系</a>
</td>
```

它**没有热度 `<span>`**（`td-01` 里是 `icon-top` 而不是名次数字）。
而 `flint/sources/weibo.py#parse_board` 现在的口径是
「`td-02` 里没有 `span` → `ParseDrift`」——**真页面一到手就会抛**。

这不是漂移，是**合成夹具从来没有过置顶行**。适配器要认这一档：
置顶行没有热度是**上游的常态**，NEVER 因此判整页漂移，也 NEVER 给它编一个热度。

真实响应已存 `fixtures/_probe/weibo/real-board.html`（105724 字节），供转回放夹具。

### 四源契约进度

`gtrends` ✅（`DEC-054` 港区代理，适配器已重建）· `weibo` ✅ **契约已探明、适配器待改**
· `ghtrend` / `arxiv` 未验（归 `CN-05`）。**这张单继续 open。**

---

## 2026-08-10 · 后两源实况（`CN-05`），**四源契约至此齐了**

### ghtrend（探测 2/10，留痕在 `fixtures/_probe/ghtrend/`）

| 端点 | 实测 |
|---|---|
| `api.github.com/search/repositories?q=created:>{day}&sort=stars&order=desc` | **200 · `application/json` · 15 repos** |

**契约没漂**：真响应喂进适配器解析出 136 条（每个 repo 由名称 / topics /
描述派生关键词）。`api.github.com` 属 `github.com` 域族，在 `DEC-052` 名单内。

### arxiv（探测 5/10）

| 查询 | 实测 |
|---|---|
| `cat:cs.AI AND submittedDate:[20260809…]`（昨天） | 200 · **`totalResults: 0`**，一条 entry 都没有 |
| 不带日期过滤 | 200 · `totalResults: 193472` |
| `submittedDate:[20260802…]`（一周前那天） | 200 · **`totalResults: 120`** |

**契约没漂，日期范围写法也是对的**——2026-08-09 是**周日**，arXiv 周末不发布。

### 这一发逼出的真问题

昨天那份回 0 条时，适配器**安安静静地回 `[]`**。而
「那天确实没有」「查询写坏了」「上游改了结构」**三种情形在盘上长得一模一样**——
当时唯一能分辨的办法是人工再打两发。

`CN-05` 把 `opensearch:totalResults` 接进解析：
**它在且为 0 = 查过了、那天没有；它整个不在 = 上游换了结构**（抛 `ParseDrift`）。

### robots 快照（`K2-01` RECORD_ONLY：照实记录、不阻断、NEVER 重判）

`fixtures/robots/ghtrend-2026-08-10.txt`（2274 字节）·
`fixtures/robots/arxiv-2026-08-10.txt`（5854 字节）。

### 这张单**继续 open**——四源契约齐了，而它的根因不止契约

`CN-05` 一度把它关掉，**关早了**：

1. 卡面 acceptance④ 写的是「**更新**这两源的实况」，不是「关掉」；
2. `tests/v041/test_blocked_sheets_state.py` 有一条判据逐字钉着
   「`K1-02` 的根因（**拿不到数据源令牌**）没有消失」——
   而四源契约探明**不等于**那件事解决了：今天四源全部走**免登录路**
   （weibo 走访客握手、gtrends 走公开 RSS、ghtrend 走未认证的 search API、
   arxiv 走公开 Atom API），而未认证的额度与稳定性都是上游随时可以收紧的。

**契约这一面已经齐了**：`weibo`（`CN-04`，访客握手 + 真榜四种行）·
`gtrends`（`CN-04`，港区 RSS）· `ghtrend` / `arxiv`（`CN-05`）。
**令牌那一面没有动过**，所以这张单照旧开着。



## 补记：免登录额度**第一份真实数字**（2026-08-11，`GATE1-REAL`）

这张单一直写着「未认证的额度与稳定性都是上游随时可以收紧的」。
`DEC-057` 那一跑（Gate① 第一次打真实网络）拿回了数字——**真响应头逐字**：

```
x-ratelimit-limit: 10          ← GitHub 免登录搜索，每分钟
x-ratelimit-remaining: 9 → 8 → 7 → 6
```

**那一跑用掉 4 发**（github 那一路只占 28 发里的 4 发）。

`GATE1-DEDUP` 修好重复取数之后，同一次分析的 github 请求降到 **2 发**——
离每分钟 10 发的天花板还远。

### owner 2026-08-11 裁决：本版**不配** token

理由（逐字）：github 今天只占 4 发、去重后 2 发，离天花板还远；
配 token 解决的是**并发**，而今天是单人测试；
token 免费但**是凭据**，存放/轮换/泄漏面都要新建，
且与本仓「NEVER 读任何 API key」的现行纪律冲突。

留下的两样：

1. **这份真实数字**（本节）——NEVER 再只写「额度是上游能收紧的」这种话；
2. **代码里一个读得出的接缝**：`flint/evidence/search.py#GithubArxivSearcher`
   的 `auth_headers` 参数，今天注入的是**空**。
   注释写明「配 token 时从这里进，NEVER 在本文件里读 env」。

### 重启条件（owner 逐字）

- 出现**第二个并发用户**；**或**
- **一次分析的 github 请求数达到两位数**。

到那时回来找 owner 要凭据裁决，**NEVER 自行开通**。
