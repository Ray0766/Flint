# GRAPH-09 trace — 框选 + ⌘A + 批量角色（批量路径主唯一仍生效）@2026-08-03

## 1 装载清单（§2.3）

- `CLAUDE.md#S2+S3`、`worker.md`、卡片 `tasks-v04.json#GRAPH-09`；
- context_refs：`WORKORDER-v04.md#5-F`（F11 行）、`contracts_v04/`（I12-1 语义，本卡未新增类型）；
- 前置产物：`web/components/graph-roles/GraphRoles.tsx`（GRAPH-06 的「主由服务端定」口径）、
  `flint/graph/roles.py`（临界区在服务端这一侧）、`web/test-utils/source.ts`（GRAPH-08 抽的共享口径）。
- 实测装载 ≈ 6k tokens，未超 40k。

## 2 关键设计判断

**批量是另一条路**。主唯一在单个路径上（GRAPH-06）已经守住了，但一次选中八个节点点
「设为主」，很容易实现成「给八个都打上 primary」——那之后图里有八个主，I12-1 破了，
**而界面上看不出来**：每个节点都显示自己是主。所以 acceptance 这一条要单独验。

**一次请求 + 只呈现回值**：整份选中项一次交给服务端（它在临界区里定主），
前端 NEVER 自己挑「最后一个」。前端挑的那个与服务端定的那个只要有一次不一致，
用户看到的就是错的。测试里专门反着来：选中顺序是 n-1,n-2,n-3 而服务端说主是 **n-1**，
界面必须听服务端的；另配一条源码断言禁掉 `selected[selected.length - 1]` 这种本地推断。

**框选是加选不是替换**：替换的话用户第二次框选就丢了第一次的，而他多半是想凑一批。

**⌘A 只选画布内的节点**：把不在图里的东西也选上，随后的批量操作会作用到用户
根本没看见的对象上。

**空批量不发请求**：一个不含任何项的批量操作没有语义（与 FAV-05 同一条口径）。

## 3 acceptance ↔ 测试映射

acceptance 唯一条：**批量设 primary 时仍只留最后一个为主（约束穿透断言）**。

| 测试名 | 覆盖点 |
|---|---|
| `批量设 primary：一次请求、带全部选中项与角色` | `toHaveBeenCalledTimes(1)` + 参数逐字（NEVER 拆成 N 次各自设主） |
| `约束穿透：批量之后图里仍只有一个主` | 被标成主的节点**恰一个**，且就是服务端说的那个 |
| `主由服务端定，前端 NEVER 自己挑「最后一个」` | 服务端故意回一个非末位的 id + 源码断言无本地推断 |
| `批量设次要/辅助不产生主` | 回值无主时界面上零个主 |
| `没选中任何节点时不发批量请求` | 空批量无语义 |
| `批量失败不谎报` | 出错误态且主标记不变 |
| `框选把框内的节点选上，框外的不动` / `再框一次是加选` / `⌘A 全选只选画布内` / `Esc 清空` | 选择本身四条 |
| `文案 key 化` | 走 GRAPH-08 抽的共享 `codeOnly` |

## 4 verify

```
$ cd web && npm test -- --run components/graph-multiselect  → 11 passed
$ npm test -- --run                                          → 226 passed / 33 files
$ npm run typecheck                                          → 干净
$ node tools/i18n_scan.mjs web/components --fail-on-cjk      → exit 0
```

禁用词扫描：本卡两份产出 0 命中。

## 5 产出

- `web/components/graph-multiselect/GraphMultiSelect.tsx`、`GraphMultiSelect.test.tsx`（11 条）
- `web/messages/{zh,en}.json`：各 +3 key（54 键，键集一致）
