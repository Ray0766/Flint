# `CN-04` weibo：**四条免登录路全部要访客凭据**

**状态** closed · 2026-08-10 · `CN-04`

**开单人**：worker，第 10 批（2026-08-10）。**依据**：`CN-04` acceptance 逐字——
「**若所有免登录路都要凭据 → 停下开单报 owner**，NEVER 静默引入登录态或硬编任何 cookie」。

## 探测实况（`DEC-052` 窗口内，5/20 额度，留痕在 `fixtures/_probe/weibo/`）

| # | 端点 | 结果 |
|---|---|---|
| 1 | `s.weibo.com/top/summary?cate=realtimehot`（带浏览器 UA、跟随重定向） | **302 → `passport.weibo.com/visitor/visitor`**（新浪访客系统） |
| 2 | `weibo.com/ajax/side/hotSearch`（卡面候选一） | **403** `{"error":"Forbidden"}` |
| 3 | `m.weibo.cn/api/container/getIndex?...realtimehot`（卡面候选二） | **302 → `visitor.passport.weibo.cn/visitor/visitor`** |
| 4 | `weibo.com/ajax/statuses/hot_band` | **403** `{"error":"Forbidden"}` |
| 5 | `s.weibo.com/top/summary`（去掉 query，排除参数问题） | **302 → 同 1** |

`CN-01` 那次报的 302 **不是因为不跟随重定向**——跟着走之后落地的是访客系统页面
（`Sina Visitor System`，正文是一段要执行的 JS）。**加 UA 不解决**：五发全带浏览器 UA。

## 为什么不自己把访客 cookie 拿下来

新浪访客系统可以用两次 POST 换一个 `SUB` 访客 cookie。**worker 没有做这件事**，理由：

1. 卡面写死「NEVER 静默引入登录态或硬编任何 cookie」。访客 token 不是账号，
   但它是**程序化铸造出来的凭据**——与「免登录路」不是一回事；
2. `DEC-052` 的边界里写着「NEVER 登录凭据」。访客握手算不算，
   **该由 owner 说，不该由我替他解释宽一点**；
3. 那条路要模拟浏览器指纹（`window.use_fp` / `fp/1.2.1.umd.js`），
   做出来就是一个**反爬对抗**件——它会随对方改动而碎，而碎的那天广场会静静地空掉。

## 需要 owner 的一句话（三选一）

1. **「访客握手可以做」** → worker 实现两步握手拿访客 cookie，
   写清它是访客态不是登录态，并给它单独的失效判据（握手挂了要能分辨出来）；
2. **「weibo 这一版先不要」** → 四源降三源，广场如实标「本版无微博」，
   `DEC-045` 的中国区口径不变；
3. **「换一个中文热榜源」** → 那是一次**新的源选型**，要新的域名授权
   （`DEC-052` 的域名族是写死的四家）。

**worker 倾向 ②**：本批的目标是「广场换成真热点」，微博缺席时另外三源仍然能出真数据；
而 ① 的产出是一个会碎的对抗件，它碎的时候没有人会收到通知。

## 绕行现状

**一行适配器代码都没改**（`flint/sources/weibo.py` 一字未动）。
探测留痕五份在 `fixtures/_probe/weibo/`，`K1-02` 已记下这五条的实况。

---

## 关闭（`DEC-053` / `CN-04`）

owner 2026-08-10 答复：**授权实现访客系统匿名握手**（两次 POST 动态取访客 cookie）。

worker 当时倾向「这一版先不要 weibo」，owner 选了另一条，并**明写接受两条真实代价**：
①反爬对抗件会碎——碎了广场如实降级，本版没有推送告警；
②平台条款风险由 owner 承担（合规照 `K2-01` RECORD_ONLY 照记）。
**这两句是本条与「悄悄做了」的分界线**，NEVER 在转述里省掉。

边界四条逐字进 `DEC-053`：cookie 值每次动态获取 NEVER 硬编 · 指纹参数集中一处并在文件头注明「上游对抗件，预期会碎」· 失败如实 `DegradationNote` 且当日补跑不超`DEC-052` 额度 · **授权上限就是访客握手，NEVER 升级成账号登录**。

五条免登录路的实测留在本单正文里——它们记的是**当时缺什么**，NEVER 因为有了答案就抹掉。
