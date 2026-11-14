# `CN-04` gtrends：端点活着，**而它没有中国区**

**状态** closed · 2026-08-10 · `CN-04`

## 探测实况（`DEC-052` 窗口内，7/20 额度，留痕在 `fixtures/_probe/gtrends/`）

| # | 端点 | 结果 |
|---|---|---|
| 1 | `trends.google.com/trending/rss?geo=CN` | **400 Bad Request** |
| 2 | `trends.google.com/trends/trendingsearches/daily/rss?geo=CN` | **404** |
| 3 | `trending/rss?geo=CN&hl=zh-CN` | **400** |
| 4 | **`trending/rss?geo=US`** | **200 · `text/xml`** |
| 5 | `trends/api/dailytrends?hl=zh-CN&tz=-480&geo=CN`（`CN-01` 打的那条） | **404**（已下线，`CN-01` 的判断属实） |
| 6 | `trending/rss?geo=HK` | **200** |
| 7 | `trending/rss?geo=TW` | **200** |

**两件事分开说**：

- **旧端点确实死了**（#5 404）——`CN-01` 那次的结论没错；
- **新端点是活的**（#4/#6/#7 200），结构也够用：
  `<item>` 里有 `<title>` 与 `<ht:approx_traffic>`（热度，形如 `200+`）、`<pubDate>`。

**卡住的是第三件事：`geo=CN` 回 400，而 `US`/`HK`/`TW` 回 200。**
Google Trends **不提供中国大陆区**——这不是一个可以修的适配器缺陷，是数据源本身的边界。

## 与 `DEC-045` 撞上了

`DEC-045` 定的是**本版只做中国区**。而 gtrends 能给的中文区只有 HK / TW，
**那是另外的地区**，不是中国大陆。拿 HK 的榜当「中国热点」显示，
就是用一个看起来对的答案盖住口径不符——本仓一路在拦的正是这种事。

## 需要 owner 的一句话（三选一）

1. **「gtrends 这一版先不要」** → 四源降三源（若 weibo 也停，则降两源），
   广场如实标缺哪一源，`DEC-045` 的中国区口径不变；
2. **「用 HK/TW 顶上，并在屏上写明它是港台区」** → 那是**改 `DEC-045` 的口径**，
   要落一条新 DEC 说明为什么这一源的地区与其余不同；
3. **「gtrends 保留接线，恒降级」** → 端点接新的 RSS、`geo` 留空跑不出中国数据，
   每天如实记一条 `DegradationNote`。**worker 不建议**：
   一条永远降级的通道与一条没接的通道，在屏上长得一样，而它每天都要花一次请求。

**worker 倾向 ①**。

## 绕行现状

**适配器一行没改**（`flint/sources/gtrends.py` 一字未动）——
新端点的解析要等 owner 定了地区口径再写，否则写出来的解析器服务的是一个未定的对象。
`K1-02` 已记下新端点的真实结构与这七条实况。

---

## 关闭（`DEC-054` / `CN-04`）

owner 2026-08-10 答复：**采 `geo=HK` 的 trending RSS，`region` 落 `CN`**——
「本版中国区」的 Google 信号定义为华语圈港区榜代理。owner 选的是本单三个选项之外的一条：
worker 反对的是**无标注冒充**，owner 的答复是**把标注做上屏**，不是取消标注。

诚实性由三件东西扛，缺一即 `review_failed`：①`DEC-054` 文本明写代理；
②provenance manifest 记真实 `geo=HK` 的 URL；③屏上署名显示「Google 趋势（港区）」。
退出条件同样写死：**下一版做多区时本代理口径撤销、改真区**。

落地见 `flint/sources/gtrends.py` 与 `tests/v041/test_cn04_source_repair.py`
（14 条判据全部离线回放当天抓的真响应，三件东西各有一条钉着）。
