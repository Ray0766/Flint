# DESIGN-17 trace — 模型选择 + 推理强度（零硬编码模型名）@2026-08-03

## 1 装载清单（§2.3）

- `CLAUDE.md#S2+S3`、`worker.md`、卡片 `tasks-v04.json#DESIGN-17`；
- context_refs：`WORKORDER-v04.md#5-G`（G23 一行）；
- 前置产物：`tools/i18n_scan.mjs`（扫描器写法与注释口径）、`web/test-utils/source.ts`。
- 实测装载 ≈ 7k tokens，未超 40k。

## 2 一处 DEC-007 遗漏（本卡顺手补齐，记 DEC-016）

卡上 verify_cmd 原写 `node tools/no_hardcoded_models.mjs web/src`——而 `web/src`
**并不存在**（DEC-007 已把前端根定为 `web/`）。DEC-007 的机械模式是
`web/src/<x>` → `web/<x>`，**末尾不带路径段的裸 `web/src`** 没被命中，
于是 `DESIGN-17` 与 `DESIGN-23` 两条 verify_cmd 留到了现在。

照原样跑会因为目录不存在而失败——那种红查起来像「工具坏了」，实际是路径写错了。
已补齐 4 处（tasks-v04.json 2 + WORKORDER 2），DAG 复跑 acyclic / errors []。

## 3 关键设计判断

**代码里一个模型名都没有**：模型会换。写死在某个组件里的型号，换代那天要靠人
去全仓找——找漏一处，那一处就永远用着旧模型，而界面上看不出任何区别：
它照样出结果，只是比别处差一档，账单也不一样。

**连默认值都由配置说了算**：组件替配置挑一个「先用这个」，就等于又写死了一次。

**配置缺失时不猜**：没有可选模型就明说未配置，而不是回落到某个「常用型号」——
回落的那一刻，用户以为自己在用他选的模型，实际上不是。

**两个维度互不牵连**：换模型不动档位、换档位不动模型（两条测试各一）。
牵连的话，用户调完模型发现档位被重置，就再也不敢碰这两个下拉框。

**档位只透传，不解释**：档位含义归后端；前端替它写一套解释就会有两套说法
（源码断言禁掉 `effort === "..."` 这种本地分档）。

## 4 扫描器的三条阴性对照（实跑，不是想当然）

| 场景 | 结果 |
|---|---|
| 真的硬编码 `"claude-sonnet-5"` | exit 1 且指出文件行号 |
| 只在**注释**里写型号 | exit 0（注释里写它通常正是在说明为什么不写进代码） |
| 只在**测试文件**里写型号 | exit 0（测试要拿真实型号当样本，那正是它该干的事） |

一把见谁都放行或见谁都拦的尺子，量不出任何东西——所以三条都实跑过。

## 5 acceptance ↔ 测试映射

acceptance「列表读环境配置；扫描器零命中硬编码模型名」：

| 测试名 | 覆盖点 |
|---|---|
| `模型与档位都从环境变量读，顺序照配置` | 列表来源 |
| `没给标签就用 id 当标签` | NEVER 显示成空白一行 |
| `默认值也来自配置` | 组件不替配置挑 |
| `配置缺失时是空的，不是某个「常用型号」` | 不回落 |
| `选项来自配置，一个不多一个不少` | 渲染面 |
| `换模型时把选择原样透传` / `换档位时不改模型` | 两维度正交 |
| `没有可选模型时明说未配置` | 未配置态可见且取到词条 |
| `档位只做透传` | 源码断言无本地分档 |
| `源码里零模型名` | 组件源码级断言 |
| （命令行） | `node tools/no_hardcoded_models.mjs web` → 73 源文件、0 处 |

## 6 verify

```
$ cd web && npm test -- --run design/model-picker  → 11 passed
$ node tools/no_hardcoded_models.mjs web            → 0 处，exit 0
$ npm test -- --run                                  → 428 passed / 52 files
$ npm run typecheck                                  → 干净
$ node tools/i18n_scan.mjs web/design --fail-on-cjk  → exit 0
```

## 7 产出

- `web/design/model-picker/ModelPicker.tsx`、`ModelPicker.test.tsx`（11 条）
- `tools/no_hardcoded_models.mjs`
- `tasks-v04.json` / `WORKORDER-v04.md`：4 处 `web/src` → `web`（DEC-016）
- `web/messages/{zh,en}.json`：各 +1 key（82 键，键集一致）
