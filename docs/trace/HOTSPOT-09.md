# HOTSPOT-09 trace — 分享菜单（一键入台 + friend 缝 + 外链入口）@2026-08-03

## 1 装载清单（§2.3）

- `CLAUDE.md#S2+S3`、`worker.md`、卡片 `tasks-v04.json#HOTSPOT-09`；
- context_refs：`WORKORDER-v04.md#5-E`（E1~E4 四行）、
  `contracts_v04/models_v04.py#ShareLink` 与 `#share_with_friend`（第 1465~1487 行）；
- 前置产物：`flint/graph/store.py` 首 50 行（GRAPH-02 的入台幂等键口径：
  `(graph_id, source_kind, source_id)`）、`web/lib/i18n/t.ts`、`web/messages/{zh,en}.json`。
- 实测装载 ≈ 10k tokens，未超 40k。

## 2 关键设计判断

**入台走既有链路**：另开一条的坏处不是多写代码，而是**幂等键分叉**——GRAPH-02 按
`(graph_id, source_kind, source_id)` 判重，同一个热点从广场入台一次、从工作台入台一次，
若走两条链路就会在画布上出现两张一模一样的卡片，而用户以为那是两个热点。
故一条源码断言把端点形态钉死：文件里的模板串**恰好只有** `/workbenches/${workbenchId}/nodes` 一个。

**node_id 由后端给**：前端编一个 id，与库里那条对不上，后续对这个节点的任何操作都会落空。
测试断言 `onAdded` 收到的是响应体里的 `node_id`。

**friend 项点了什么都不发**：一个看起来能点、点了却悄悄失败的菜单项，比明说
「即将上线」糟得多。前端 `aria-disabled` + 词条；后端那一半抛 `NotImplementedError`。

**外链项只开入口**：点一下菜单就 `POST /share-links` 等于悄悄铸出一条**公开可读**的链接。
铸不铸由随后的确认动作决定，故菜单项只调回调、零请求（测试断言 `calls.length === 0`）。

**失败不谎报成功**：500 时不调 `onAdded`、渲染失败态。不这么做的话，用户以为已入台，
去工作台却找不到——而他不会怀疑是入台失败，只会怀疑自己记错了。

## 3 test-first 顺序

1. 后端半 `tests/v04/share/test_friend_stub.py`（4 条）先写 → 跑 → 红（文件不存在）→
   4 passed。**说明**：这一半断的是 SCHEMA-11 已落地的缝**没有走样**（形态断言 +
   仓库级「没人吞掉它」扫描），本卡未新增后端实现，与卡片 outputs 一致。
2. 前端半 8 条先写 → 跑 → 红（`Failed to resolve import "./ShareMenu"`）；
3. 实现 `ShareMenu.tsx` + 4 条 i18n key → 8 passed。

## 4 acceptance ↔ 测试映射

**① 入台项调 GRAPH-02 端点（E1 零新链路）**

| 测试名 | 覆盖点 |
|---|---|
| `入台项调 GRAPH-02 端点` | 方法 POST、URL `/workbenches/wb-1/nodes`、body `{source_kind, source_id}` 逐字 |
| `零新链路：源码里只有这一个端点形态` | 源码模板串集合**恰等于**单元素列表（多一条入台路径立刻红） |
| `入台成功后把 node_id 交给调用方` | 回调收到后端给的 id，前端 NEVER 自己编 |
| `三项都在，且入台恒为第一项` | E1「菜单第一项就是入台」 |
| `入台失败不谎报成功` | 500 → 回调未被调用 + 失败态可见 |

**② friend 项渲染「即将上线」且后端抛 NotImplementedError**

| 测试名 | 覆盖点 |
|---|---|
| `friend 项渲染「即将上线」且不可点` | `aria-disabled=true`、文案取到词条（非 key 回落）、**点它零请求** |
| `test_share_with_friend_raises_the_exact_contract_message` | 消息逐字 `friends: post-v1`（前端按它分派） |
| `test_the_stub_is_a_raise_not_a_flag` | 函数体只有一个 `raise`；无 `friends_enabled` 类开关字段 |
| `test_nobody_swallows_the_stub` | **仓库级**扫描：`flint/` 下没有任何 `except NotImplementedError` |
| `test_share_link_keeps_expiry_and_revocation_apart` | 过期与撤销不合并（撤销不可逆，合并后一次续期会让被撤销的链接复活）；无明文口令字段 |

「没人吞掉它」那条是这一半最值钱的：吞掉之后「分享给朋友」在界面上看起来成功了，
而什么都没发生——用户会以为对方收到了。

## 5 verify（卡上 verify_cmd 是合取，两段分别在各自 cwd 跑）

```
$ cd web && npm test -- --run components/share-menu   → 8 passed
$ pytest tests/v04/share/test_friend_stub.py -q        → 4 passed
```

回归：前端全套 **178 passed / 28 files**、typecheck 干净、
`i18n_scan web/components` exit 0；`pytest tests/v04/share` 18 passed；
`ruff` 全绿；`mypy --strict flint` 255 文件净。

## 6 产出

- `web/components/share-menu/ShareMenu.tsx`、`ShareMenu.test.tsx`（8 条）
- `tests/v04/share/test_friend_stub.py`（4 条）
- `web/messages/{zh,en}.json`：各 +4 key（33 键，键集一致）
