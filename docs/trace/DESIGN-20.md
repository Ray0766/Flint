# DESIGN-20 trace — 依赖白名单（越界剥除 + 报错）@2026-08-03

## 1 装载清单（§2.3）

- `CLAUDE.md#S2+S3`、`worker.md`、卡片 `tasks-v04.json#DESIGN-20`；
- context_refs：`WORKORDER-v04.md#5-G`（G26 一行）；
- 前置产物：`web/design/renderer/SrcdocRenderer.tsx`（DESIGN-02 的「安全靠沙箱不靠改写」）、
  `web/design/ds-mount/dsMount.ts`（`_ds` 自托管落点）、`web/test-utils/source.ts`。
- 实测装载 ≈ 6k tokens，未超 40k。

## 2 与 DESIGN-02 的边界（两条看似冲突的纪律，其实管的不是一件事）

DESIGN-02 说「**安全靠沙箱，不靠改写内容**」，本卡却要剥掉外部引用——不矛盾：

- 沙箱管的是**这段代码能干什么**（不给同源、不给顶层跳转）；
- 白名单管的是**产物向谁要东西**。一个 `<script src="https://cdn…">` 即使跑在沙箱里，
  也仍然会在**客户机器上**向第三方发请求：网络不通时页面塌掉、内容被对方看见、
  而且哪天那个 CDN 改版，早已交付的文件会自己变样。

所以剥除只发生在**交付面**（样板/产物的外部引用），预览面照旧原样直挂。
**内联 script 不动**：它不向外发请求，剥了反而毁掉页面自己的逻辑。

## 3 关键设计判断

**剥完必须报，且说得出「换成什么」**：静默剥除会让作者以为图表功能好好的，
直到客户打开一个空白框。只说「剥了」也不够——那是把问题原样丢回给他；
`action` 明写「改用自托管资产（放 `_ds` 或内联）」。

**协议相对 `//cdn…` 单独测**：它看起来像路径，实际是外部来源——最容易漏的一种写法。
`data:` / `blob:` 同样剥：产物里嵌一段来路不明的可执行内容同样不该有。

**白名单不是「一律剥光」**：同源与 `_ds` 资产保留，自定义白名单可放行企业自托管镜像。
配一条阴性对照（干净样板原样返回）——一把见谁都剥的尺子会逼人绕过它。

**剥除只动那一个标签**：周围内容逐字不变，剥完留下的空行一并收拾
（否则产物里会多出一片莫名其妙的空白）。

## 4 acceptance ↔ 测试映射

acceptance「白名单外 script/link 剥除并报错列出」：

| 测试名 | 覆盖点 |
|---|---|
| `剥掉外部 script，并报出剥了什么` | 剥 + 清单 |
| `剥掉外部 link（样式表/字体）同样报出来` | link 面 |
| `同源与 _ds 资产保留` | 白名单不是一律剥光 |
| `内联 script 不动` | 管的是「向谁要东西」 |
| `协议相对与 http 都算外部` | 最易漏的写法 |
| `data: 与 blob: 也剥` | 来路不明的可执行内容 |
| `剥除只动那一个标签` | 周围逐字不变 + 空行收拾 |
| `自定义白名单可放行指定来源` | 自托管镜像场景 |
| `干净的样板原样返回` | 阴性对照 |
| `剥除清单说得出「换成什么」` | action 取到词条 |
| `源码代码行零 CJK` | 共享 `codeOnly` |

## 5 verify

```
$ cd web && npm test -- --run design/dep-whitelist  → 12 passed
$ npm test -- --run                                   → 452 passed / 54 files
$ npm run typecheck                                   → 干净
$ node tools/i18n_scan.mjs web/design --fail-on-cjk   → exit 0
```

禁用词 0；产出均为 LF。

## 6 产出

- `web/design/dep-whitelist/depWhitelist.ts`、`depWhitelist.test.ts`（12 条）
- `web/messages/{zh,en}.json`：各 +1 key（84 键，键集一致）
