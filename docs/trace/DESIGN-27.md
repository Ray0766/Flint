# DESIGN-27 trace — [隔离·G2] 样板可辨识三件套@2026-08-03

> **隔离带卡 + owner_review**。按 DEC-000：默认照做、完成后打标继续。
> 开工前复查 `DECISIONS-v04.md` 无划除记录；工单 §11-② 明写「建议列为不可谈判项」。

## 1 装载清单（§2.3）

- `CLAUDE.md#S2+S3`（三条铁律：数字必有出处）、`worker.md`、卡片 `tasks-v04.json#DESIGN-27`；
- context_refs：`WORKORDER-v04.md#11`（②样板可辨识全文）、`WORKORDER-v04.md#5-G`（G2 行）；
- 前置产物：`web/design/renderer/SrcdocRenderer.tsx`、
  `web/components/source-columns/synthesis-blacklist.json`（「检测模式放 .json」的先例）、
  `web/test-utils/source.ts`。
- 实测装载 ≈ 7k tokens，未超 40k。

## 2 为什么这三件是**不可谈判**的

探索期样板里的示例数字（「渗透率 42.7%」）一旦被截图外传当成真报告，
燧石「每个数字有出处」这条立身之本当场破产——而外传的人往往**不知道自己拿的是样板**。
三件套要保证：无论从哪个出口流出去，它都自带「这是样板」这句话。

- **占位语法**：`XX.X%` 一眼假，`42.7%` 看起来就是真的；来源同理（`SRC-XXXX` vs `SRC-1234`）。
- **水印不可移除**的可执行化 = 渲染与导出在看不到水印节点时**拒绝**，而不是补一个回去。
  补回去等于告诉调用方「你怎么改都行，我兜着」，而这条规则的全部意义是**它兜不住**。
- **`-mock` 后缀**：截图外传拦不住，但发文件时它就在标题栏上。

## 3 两次修（一次实现 bug，一次已知假阳性）

**实现 bug（测试逼出来的）**：`SRC-1234` 同时命中「具体来源」与「具体数字」两条规则——
同一个问题报两遍。用户改完一处发现清单还剩一条，会以为自己没改对。
改法：先摘出具体来源、把它们的位置**空格化**，再在剩下的文字里找具体数字。

**已知假阳性**：四条检测模式含中文（`[来源待补]`），被 `i18n_scan` 判为未 key 化——
按 HOTSPOT-07 的先例移进 `mock-syntax.json`：它们是**检测模式**不是界面文案，
中文要逐字保留（key 化会让它们不再匹配任何东西）。另一段 JSDoc 改行注释，
避开跨行块注释的已知假阳性（DEC-013 / `I18N-09`）。

## 4 自审报告（§4.6，本卡 self_review=true）

**①** acceptance ↔ 测试：

| acceptance | 测试名 |
|---|---|
| 占位语法强制 | `占位数字与占位来源都被认作合规`、`具体数字被抓出来`、`具体来源编号也被抓出来`、`违规清单逐条列出` |
| 文件名 `-mock` | `isMockFilename` 参数化四条（含 `mock-proposal.html` 这种前缀伪装） |
| 水印缺失 → 拒绝 | `缺水印 → 拒绝`、`没有水印就是没有：NEVER 补一个回去`（含源码断言） |
| 三件套缺一即拒 | `三件齐全时放行`（阴性对照）、`文件名没有 -mock → 拒绝`、`正文里有真数字 → 拒绝`、`拒绝时把所有违规列出来`、`拒绝时不返回半个产物` |

**②** 无冻结件偏离：纯前端模块，零触碰 `contracts/`。
**③** 无禁用词：三份产出 0 命中。
**④** 复用断言在位：检测模式放 `.json` 沿用 HOTSPOT-07 的口径；源码扫描走共享 `codeOnly`。
**⑤** 装载 ≈7k tokens，未超 40k。

## 5 verify

```
$ cd web && npm test -- --run design/mock-identity  → 17 passed
$ npm test -- --run                                   → 524 passed / 58 files
$ npm run typecheck                                   → 干净
$ 四把扫描器                                            → 全 exit 0
```

禁用词 0；产出均为 LF。

## 6 产出

- `web/design/mock-identity/mockIdentity.ts`、`mockIdentity.test.ts`（17 条）、`mock-syntax.json`
