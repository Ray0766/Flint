# `CN-04` gtrends：适配器换了端点，**34 天的回放夹具还是旧那条**

**状态** closed · 2026-08-10 · `CN-04`

## 现象

`DEC-054` 让 gtrends 从 `trends/api/dailytrends`（JSON）换到
`trending/rss?geo=HK`（XML）。适配器已重建、离线判据 14 条全绿、
`ruff` / `mypy --strict flint`（319 文件）全绿。

**而回放层还停在旧契约上**：

```
respx.models.AllMockedAssertionError:
  <Request('GET', 'https://trends.google.com/trending/rss?geo=HK')> not mocked!
flint.testing.replay.ReplayMiss:
  no recorded exchange for GET https://trends.google.com/trending/rss?geo=HK
```

实测 `pytest tests/m1 tests/fe_views -q` → **17 failed, 334 passed, 19 errors**。

## 根因不是缺陷，是契约变了

`fixtures/gtrends/*.json` **34 天**每一份都按 URL 键存着录制：

```json
{"method":"GET","url":"https://trends.google.com/trends/api/dailytrends?hl=zh-CN&geo=CN&ed=20260624",
 "content_type":"application/json; charset=UTF-8","body_text":")]}'
{\"default\": {...}}"}
```

三样都得跟着换：**URL 键** · **content_type**（→ `text/xml`）· **body 形状**（JSON → RSS）。
它们由 `fixtures/_generate_4src.py`（284 行）生成，
其中 gtrends 那一族是 `gtrends_url()` / `gtrends_body()` 两个函数 + 注册表一行。

## 为什么停在这里

`CN-04` 的 outputs 是 `flint/sources/` · `fixtures/_record_cn_real.py` ·
`fixtures/_probe/` · `tests/v041/test_cn04_source_repair.py` ·
`docs/blocked/K1-02-…`。**`fixtures/_generate_4src.py` 与 `fixtures/gtrends/` 都不在里面**，
而本批 rules 写死「改动面大于卡上 outputs → 停下走 `docs/blocked/`」。

这与 `SHELL-02` 那次停下**不同**：那次卡的是一条只有 owner 能定的口径。
这次**没有口径要定**——`DEC-054` 已经把端点与形状定死了，
要的只是一句「outputs 加上这两处」。

## 需要 steward / owner 的一句话

**「`CN-04` 的 outputs 加上 `fixtures/_generate_4src.py` 与 `fixtures/gtrends/`」**
→ worker 改 `gtrends_url` / `gtrends_body` 两个函数（RSS 形状照
`fixtures/_probe/gtrends/real-hk-rss.xml` 那份**真响应**写）、重跑生成器出 34 天，
再跑 `tests/m1` 与 `tests/fe_views` 回绿。

**另一条路 worker 不建议**：把新旧两条 URL 都接受。那等于在取数路上留一条
今天回 404 的备用路，而下一个人会以为它还能用。

## 绕行现状与**当前盘上的红**（据实记，NEVER 藏）

- 适配器与新判据**已落盘且全绿**（`tests/v041/test_cn04_source_repair.py` 14 条）；
- `tests/m1` + `tests/fe_views` **17 failed / 19 errors**，全部同一个根因（上面那条）；
- `ruff` · `mypy --strict flint` 全绿；
- **weibo 半（`DEC-053` 访客握手）本轮一行未写**——它与本单无关，
  是 worker 的上下文用尽，不是被什么挡住。

---

## 关闭（`CN-04`）

steward 2026-08-10 把 `fixtures/_generate_4src.py` 与 `fixtures/gtrends/` 加进 `CN-04` 的 outputs，
并把护栏写进 acceptance：**重生成 MUST 只换 HTTP 信封，34 天的词面与数值 NEVER 变**。
双 URL 备用路按 worker 的建议**拒绝**。

落地：`gtrends_url` 换成 `trending/rss?geo=HK`（不吃日期，所以 34 天 URL 键相同——
夹具按天分文件、回放先按天取文件再按 URL 取那次往返，这是对的）；
`gtrends_body` 换成 RSS，形状照 `fixtures/_probe/gtrends/real-hk-rss.xml` 那份真响应写；
`content_type` → `text/xml; charset=UTF-8`。**词面与热度沿用同一个 `_gt_queries(day)`
与同一个公式**，所以数据一个字没动。

**护栏实测**：改前把 34 天的（词面, 热度串）逐日抄成基线，重生成后逐日比对——
32 天 200 响应**零差异**，另两天的非 200 状态码也没变。

回绿：`tests/m1` + `tests/fe_views` 从 **17 failed / 19 errors** 到 **370 passed**。
其中三条不是 `ReplayMiss`，是**旧契约的断言**，逐条翻面并写明为什么：
`test_m1_015` 的 URL 表还指着 dailytrends；`test_m1_009` 断言 `)]}'` 反劫持前缀与
`"trendingSearches"` 键——那两样是旧信封的形状，而那条判据要守的东西一字未变：
**夹具保留每一源自己的原生形状**。全量 `pytest -q` = **5042 passed / 0 failed**。
