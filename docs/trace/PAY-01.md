# PAY-01 · 托管收银台接入方案调研（档 A 只读）

**卡** `docs/steward/tasks-v041-b2.json#PAY-01` · **cycles 2** ·
**self_review = true** → §6 · **owner_review = true** → §7
**依赖** SHIP-01（verified）

## 1. 装载清单

卡面 PAY-01 · `CLAUDE.md#S1`（V1 范围含支付）· `flint/billing/quota.py` 全文
（「配置留空 = 整条计费路径关闭」那条口径）· `DECISIONS-v04.md#DEC-024` 全文 ·
本轮实读的五个官方页（见 §3）。约 11k tokens，预算 40k 以内。

## 2. 这张卡最要紧的不是写得好，是**不把没查到的写得像查到的**

一份调研文档最容易出的问题不是文笔，是**记忆冒充调研**。
「微信费率 0.6%」这种句子写出来毫无违和感，而它既没有出处，也不知道是哪一年的。

所以文档的形状是一张 **四家 × 五维度 = 20 格** 的表，每格六列：
收银台 / 维度 / 查到的内容 / 官方出处 / 查阅日期 / **读没读到**。

最后一列只有两个值：**实读**（本轮真把那页取下来读到了那句话）与
**未读到**（页面在商户后台之后、或正文由 JS 渲染，`WebFetch` 只拿到标题）。
判据钉死三条：

- 未读到的格子里 **NEVER 出现百分比或 T+N**；
- 未读到要写**为什么**（要登录 / JS 渲染 / 页面没这一段），只写四个字不算；
- **标记与格子正文 NEVER 互相矛盾**（这一条是变异考逼出来的，见 §5）。

## 3. 实际读到了什么、没读到什么

**读到了（5 个页面，11 条链接全部实测 200）**：

| 页面 | 读到的关键内容 |
|---|---|
| 微信 JSAPI 下单文档 | `POST /v3/pay/transactions/jsapi`、主备域名、`prepay_id` 有效期 2 小时、`notify_url` |
| 微信支付通知文档 | AES-256-GCM 加密报文、四个验签头、200/204 应答、5 秒时限、**15 次重试的完整间隔表** |
| PayPal Webhooks | 两种验签路径、四个 `paypal-*` 头、`/v1/notifications/verify-webhook-signature`、2xx 应答、**3 天 25 次重试** |
| PayPal 费率页 | 3.49% + 0.49 USD（境内）、跨境 +1.50%、货币转换 4.00%（部分 3.00%）、月费 "No fee" |
| Apple Pay 实现页 | 官方原话「Use an Apple Pay SDK from a payment service provider」、Merchant ID + 商户身份证书 + 域名验证 |

**没读到（并且没有编）**：

- **微信的费率与结算周期**——费率协议页在登录态之后，本轮拿到的只有产品导航与客服电话；
- **支付宝的全部五格**——`opendocs.alipay.com` 与 `b.alipay.com` 的正文都是 JS 渲染，
  `WebFetch` 只拿到「小程序文档 - 支付宝文档中心」这一个标题。
  接口名 `alipay.trade.page.pay` 与「回校 `out_trade_no` / `total_amount` /
  `seller_id` / `app_id` + RSA 验签」来自 `WebSearch` 的结果摘要，
  **不是逐字读到的**，所以那两格标的是「未读到」；
- **PayPal 的结算周期**——费率页没有那一段；
- **Apple Pay 的回调与费率**——它不是收单方，这两件事由背后的 PSP 决定。

**这就是本卡最有价值的产出之一**：它明确告诉 owner「哪几格还要你登录后补」，
而不是给一份看起来完整、其中一半靠记忆的表。

## 4. 选型结论（一句话版）

**三家是收单方，一家不是。** Apple Pay 官方让你用支付服务商的 SDK——
它是**前端的一种付款方式**，背后仍要挂 PSP，不能与前三家并列比较。

- **中国用户 → 微信支付**：回调规格本轮读全了（加密、四头、应答、时限、重试表），
  接线时不用再猜；支付宝排第二**不是因为它差，是因为我们对它的了解还不够动手**。
- **海外用户 → PayPal 标准 Checkout**：四家里唯一读到确数费率的，且注册门槛最低
  （无月费无开通费）——K7/K8 定价未定期间最合适。
- **Apple Pay → 不单独接**，等海外线选定 PSP 后跟着开。
  没有 PSP 的 Apple Pay 是个接不上收单的按钮。

两条路径**各自**写清了需要 owner 提供什么（营业执照 / 对公账户 / 商户号 mchid /
APIv3 密钥 · PayPal 商务账户 / `client_id` / `client_secret` / Webhook ID），
**全部属红线，本卡 NEVER 自行申请**。

## 5. 变异考：十九个，两个先活了下来

| 变异 | 抽掉什么 | 结果 |
|---|---|---|
| ① 删掉 Apple Pay 那四行 | 四家全覆盖 | **1 failed** ✓ |
| ② 删掉一整个维度格 | 20 格全在 | **1 failed** ✓ |
| ③ 未读到的格里填一个记忆里的费率 | §2 的核心 | **1 failed** ✓ |
| ④ 未读到的格里填一个结算周期 | 同上 | **1 failed** ✓ |
| ⑤ 把「未读到」偷偷改成「实读」 | 同上 | **20 passed** ✗ → 补判后 **1 failed** ✓ |
| ⑥ 未读到只写四个字 | 说清为什么 | **1 failed** ✓ |
| ⑦ 出处换成第三方博客 | 官方站白名单 | **1 failed** ✓ |
| ⑧ 某行不写查阅日期 | acceptance① | **1 failed** ✓ |
| ⑨ 引一条没进实测表的链接 | 链接验过 | **1 failed** ✓ |
| ⑩ 实测表里塞一条 404 | 同上 | **1 failed** ✓ |
| ⑪ 整张表全标未读到 | 反向 | **2 failed** ✓ |
| ⑫⑬⑭ 裁决那节少写一条 | acceptance② | 各 **1 failed** ✓ |
| ⑮ 建议只覆盖一个受众 | acceptance③ | **1 failed** ✓ |
| ⑯ 建议不写要 owner 提供什么 | acceptance③ | **20 passed** ✗ → 补判后 **1 failed** ✓ |
| ⑰ 建议不写理由（只排序） | acceptance③ | **1 failed** ✓ |
| ⑱ 不写「真实接入是 PAY-02」 | acceptance④ | **1 failed** ✓ |
| ⑲ 文档里贴一个像真商户号的串 | 红线 | **1 failed** ✓ |

**⑤ 为什么能活——本卡最该记的一条**：判据原本只查「最后一列是那两个词之一」。
把某一格的「未读到」改成「实读」之后，那一格的**正文还写着「本轮未取到字段表」**，
而标记说读到了——**判据看不出这个矛盾**。

一份自相矛盾的调研比一份承认没查到的调研危险：读的人会信那个标记。
补判：格子正文里出现「未取到 / 只拿到标题 / 未逐字取到」这类说法时，
标记 **MUST** 是「未读到」——**标记与正文对不上时以正文为准**，
正文是当时写下的实况，标记只是一个字。

**⑯ 为什么能活**：判据按**整节**查「有没有出现『需要 owner 提供』」，
而 Apple Pay 那一小段顺口写的一句「届时需要 owner 提供 Apple Developer 账号…」
把它喂饱了——**把两条主推荐路径里的材料清单整段删掉，毫无反应**。
补判：按三级标题逐条切开，**每条路径各自**要有那句话。

这是本轮连跑里第五次撞上同一形状（判据的取值范围里混进了别处同一个词）。

十九次变异后文档与变异前逐字相同（baseline 20 passed）。

## 6. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_payment_plan_doc.py -q → 20 passed
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: no issues found in 288 source files
            pytest -q               → 3137 passed（DOC-03 收卡时 3117，本卡 +20）
采集期实测:  curl -o /dev/null -w %{http_code} -L × 11 条链接 → 全部 200
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① 四家 × 五维度，每条附官方链接与查阅日期 | `test_all_four_providers_are_covered`、`test_every_provider_covers_every_dimension`、`test_every_row_carries_an_official_link_and_a_date`、`test_every_cited_link_was_probed_at_collection_time`、`test_every_probed_link_answered_200` |
| ② owner 两条硬边界 | `test_the_two_rulings_are_stated_in_their_own_section` |
| ③ 两条路径各带理由与所需材料 | `test_the_recommendation_covers_both_audiences`、`test_each_recommended_path_says_what_owner_must_provide`、`test_the_recommendation_gives_reasons_not_just_a_ranking` |
| ④ 只出方案不接线 | `test_the_card_added_no_payment_dependency`、`test_the_billing_module_still_touches_no_gateway`、`test_no_real_merchant_credential_landed_in_the_repo`、`test_the_doc_says_wiring_is_the_next_card` |
| （本卡自加）读到了与没读到分开标 | `test_each_cell_declares_whether_it_was_actually_read`、`test_an_unread_cell_never_states_a_number`、`test_an_unread_cell_says_why_it_could_not_be_read`、`test_a_cell_that_admits_it_could_not_be_read_is_marked_that_way`、`test_a_cell_marked_read_really_states_a_finding`、`test_at_least_one_cell_was_really_read` |

**② 无冻结件偏离**：本卡零代码改动。`contracts/` · `flint/` · `requirements.lock` ·
`pyproject.toml` · `web/package.json` 全部未触碰（且有判据反向扫）。

**③ 禁用词**：六词在两个产物文件里 0 命中。文档里有一处「等」——
它在**微信官方页的逐字引文**里（「提交营业执照、身份证、银行账户等基本信息」），
已加引号并注明「其中的『等』属官方措辞」，不是本文件自己的含糊表述。

**④ 复用**：判据复用本轮既有的「按节判、不按全文判」写法；
链接可达性走采集期实测 + 落表，**验证期零联网**（S2-7）。

**⑤ 装载预算**：约 11k tokens，未超 40k。

**⑥ 网络纪律**：全程档 A（只读、不登录、不提交表单）。
未触发档 B（真实源抓取）与档 C（付费）。

## 7. owner_review：三件

1. **两格空白要 owner 补**：微信的费率与结算周期在商户平台登录态之后，
   支付宝的五格全在 JS 渲染页/商家中心之后。**要么 owner 登录后截给我，
   要么 PAY-02 接线时以签约页为准。** 我 NEVER 填记忆里的数字。
2. **选型建议认不认**（中国 → 微信、海外 → PayPal、Apple Pay 跟 PSP）。
   理由写在文档里，可以逐条反驳。
3. **PAY-02 需要的材料清单**（§4 括号里那几样）**全属红线**——
   开通与密钥只有 owner 本人能做，本卡与 PAY-02 都 NEVER 自行触碰。

## 8. 登记未做

1. **支付宝的正文一格都没读到**。它的开放平台文档是 JS 渲染的，`WebFetch` 无解。
   下一轮可换 `C:\pwenv` 的 playwright 真渲染再读（那仍属档 A 只读）——
   本卡没做，因为卡上要的是方案不是抓取工程。
2. **没有比较到期后的费率变动**：四家的费率页都是「当前」值，没有历史与生效日期。
3. **没有调研退款与对账**：卡上五个维度不含它们，而真接线时这两件必问。
   登记在此，PAY-02 或 PAY-03 会撞上。
4. **没有调研合规资质**（ICP / 支付业务许可的适用性）——那属法务面，
   与 COMP-01 的上线前清单是同一类东西，本卡没有并进去。
5. **一行网关代码没写**，`flint/billing/` 仍是零网关（判据钉着）。
