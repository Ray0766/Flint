# REGION-07 trace — fetch_legal_status 抓取门 + 网络护栏 @2026-08-02

## 1 装载
REGION-07 卡 + `flint/sources/degradation.py`（复用对象）+ respx 既有用法。~1,200 字符（3%）。

## 2 test-first
先写测试 → collection error → 实现 → **10 passed**；ruff 净、mypy 净。

## 3 两条判断
**① unknown 也不放行**：`FetchLegalStatus` 缺省是 `unknown`（K2 未决）。门只认 `allowed`——
**「不知道能不能抓」NEVER 等于「可以抓」**。反过来做（默认放行、出事再拉黑）意味着
第一次抓取已经发生了，而合规问题里**第一次就是全部代价**。

**② 拒绝不是静默跳过**：落 `DegradationNote` 让缺口可见。悄悄跳过会让
「这个源今天被合规门挡了」看起来像「今天没热点」——两件完全不同的事。
门用抛错而不是返回 None，就是不让调用方有「忽略返回值」的机会。

## 4 网络护栏（acceptance ②，S2-7）
- `test_real_http_call_is_intercepted`：respx 接住请求（`route.called` 为证 = 没出网）；
- `test_unmocked_host_is_refused_not_dialed`：**没登记的地址直接被拒**——
  「连不上」才是护栏，「碰巧没网」不是；
- `test_fetch_gate_module_makes_no_network_call`：源码断言门里没有
  `httpx`/`requests`/`urlopen`/`socket` —— 门若自己发一个试探请求，
  它就成了第一次越界的人。

## 5 DEC-003 边界内的既有文件改动（第二处）
`flint/sources/degradation.py` 的 `DegradationReason` 再加一值
`"fetch_denied_by_legal_status"`（E6 降级矩阵注册点，只加不删，既有值与函数语义未动）。

## 6 产出
`flint/region/fetch_gate.py`、`tests/v04/region/test_fetch_legal_gate.py`（10 条）。
