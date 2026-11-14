# DESIGN-02 · 工作台②：那一屏现在是空壳

> v0.4.1 第 5 批第九张。依赖 `DS-01`、`DESIGN-01`（均 verified）。

## 装载清单

`tasks-v041-b5.json#DESIGN-02` · `docs/前端功能说明-v2.md#2.17` ·
`web/components/design-workbench/DesignWorkbench.tsx`（全文 108 行）· `web/app/design/page.tsx` ·
`web/lib/jobClient.ts`（判别联合镜像 + `applyEvent` + `openJobStream`）·
`web/components/plaza/cardActions.ts`（结果形状）· 真栈 openapi。约 13k tokens，**未超 40k**。

## 一、改前实况

那一屏**已经有的**：`iframe srcdoc` 预览、失败态（原始产物 + 错误）、固化键与两种阻断说明。
`page.tsx` 给它传**两个 `null`**，并且**一个请求都不发**。

**缺的两件**（acceptance① 三件里的两件）：自然语言输入区、生成中的流式区。

## 二、端点实况（开工时打过真栈）

| 端点 | 状态 |
|---|---|
| `GET /jobs/{id}/events` | **通** |
| `GET /design/sessions/{job_id}/replay` | **通**（`DESIGN-01` 刚把 `load_session` 接上，改前恒 404） |
| `POST /projects/{id}/design_generate` | **不存在**（框架那种没有 `code` 的 404） |

单据：`docs/blocked/DESIGN-GENERATE-HAS-NO-SUBMIT-ENDPOINT.md`（含两个待裁项）。

## 三、三处设计判断

### 3.1 提交那条**照样发请求**——这是把 UI-04 的口径有意翻过来

UI-04 当时判「这一屏一个请求都不发」，理由是「发一个必然 404 的请求只会留一条假红」。
今天三条里两条真通了，不发就等于把它们晾着。第三条仍然没有，而它**照样要发**：
**「能不能提交」的真相在服务端**。前端自带一份「我知道它没有」的判断，
那份判断会与后端各自漂移——端点哪天挂上了，屏上仍然显示「没有」。

代价是控制台一条 404。**登记而不是掩盖**：
`test_the_only_console_noise_is_the_registered_missing_endpoint` 判等值——
多一条要停下来看，**少一条说明端点挂上了**，那时来删那行并关单。

### 3.2 进屏 NEVER 提交，只取回

带 `?job=` 进来时先打一次 replay 拿回已产出的文字，再续订 SSE。
进屏就提交的话，用户每刷新一次页面就多开一个作业，而他看到的只是「又从头开始了」。
判据扫进屏的每个 `useEffect`，里面 NEVER 出现 `submitDesign`（本卡与 UI-04 两处各判一次）。

### 3.3 逐块拼接只有一处实现

拼接放在 `jobClient` 的 `designText` 里，屏那边只显示。
两处各拼一次的话，丢块与重块都看不出来。

## 四、改既有文件（工单纪律 4）

| 文件 | 改前 | 改后 | 为什么非改不可 |
|---|---|---|---|
| `web/components/design-workbench/DesignWorkbench.tsx` | 108 行，只有预览与固化 | +输入区 +流式区 +提交答复行；用 `DsStatusMark` 出「生成中」 | 卡面 acceptance①⑤ |
| `web/app/design/page.tsx` | 传两个 `null`，零请求 | 接 replay + SSE + 提交 | 见 3.1 / 3.2 |
| `web/lib/jobClient.ts` | 判别联合镜像少 `design_delta` | 补上成员 + `designText` 累积 | **镜像落后一个成员会当场抛**：`applyEvent` 结尾是 `assertNever`，真来一条 `design_delta` 整条流断在那里，而屏上看起来只是「不再有新内容」。**超出卡面 outputs，在此登记** |
| `web/app/globals.css` | `.design__*` 零样式 | +工作台一段；并让设计台与卡片屏一样退出 34em 阅读宽度 | 一个 428px 宽的 iframe 预览不出任何设计——那正是「预览」这件事的全部意义 |
| `web/messages/{zh,en}.json` | 无 | +7 键 ×2 | NEVER 在组件里写死中文 |
| `web/__tests__/app/ui04.test.tsx` | `querySelector("button")` 取第一个键 | 按 `.design__solidify` 点名 | 这一屏不再只有一个键（生成键在前）。**判的仍是同一件事**：注册表可用时固化能点 |
| `tests/v041/test_ui04.py` | 「一个请求都不发」+ i18n key 正则 | 翻成「进屏 NEVER 提交」；正则加词边界 | 前者见 3.1；后者是**尺子自身的毛病**：`t\\("` 会把 `.get("job")` 当成 key，报错的地方对、报的内容假 |
| `tests/v041/test_plaza_cards.py` | 段落尺子扫到文件尾 | 收敛到本段 | **与上一轮修 UI-01 那把是同一个毛病**——本卡写它时照抄了那个形状，照抄错的也是错的 |

## 五、取证（真栈 `/design`，`.ui-probe/design_workbench.json` + `design-workbench.png`）

```
prompt   1160×88   generate 62×36「生成」   stream 1160×120   preview 1160×200
真按一次「生成」：outcome kind=not_provided ·「接口未提供：生成入口还没挂」· 未跳走
console_errors 恰好一条，且是登记过的那条 404
```

截图已看过：屏头下是输入区（textarea + 黄色「生成」键），键下一行虚线框的诚实态，
再下是纸纹底的流式区（「还没有产出任何块」），再下是预览区与固化段。
全宽 1160px——改前它被 34em 阅读宽度压成 428px，预览框里什么也看不清。

## 六、verify

```
pytest tests/v041/test_design_workbench_ui.py -q  → 19 passed
pytest tests/v041 -q                              → 2367 passed / 4 failed
                                                    （4 条全是那条 403，与本批无关）
cd web && npm test -- --run                       → 77 files / 784 tests passed
cd web && npx tsc --noEmit                        → 0
ruff check . --no-cache                           → All checks passed
node tools/i18n_scan.mjs web --fail-on-cjk        → CJK 0
node tools/no_scaffold_on_screen.mjs web          → 产品面没有 A 类脚手架
python tools/check_line_endings.py                → 209 个文件全是 LF
```

返工四轮：`ui04.test.tsx` 的「第一个 button」不再是固化键 · 我自己那条「控制台干净」
与「有意发一个 404」相撞（改成登记等值）· 段落尺子扫到文件尾（与上一轮同一个毛病）·
heredoc 又把 `\\b` 写成真退格符（`ruff PLE2510` 抓到 5 处，**第二次栽在同一处**）。

## 七、self_review（worker.md §4.6）

① **测试覆盖 acceptance**：19 条对五条 acceptance；三件都在**真浏览器里量宽高**——
源码层判得出「有没有」，判不出「是不是 0 像素」（`F-09` 就是那个形状）。
「产物 NEVER 进主文档」在**整个工作台目录**上判，不是只判那一个文件——
只判一个文件的话，下一个人在旁边新建一个渲染器就绕过去了。
② **无冻结件偏离**：`contracts/` 一字未动；TS 镜像补的成员与 `contracts_v04` 逐字一致。
③ **无禁用词**：grep 零命中。
④ **复用断言在位**：结果形状复用 `ActionOutcome`（`test_the_submit_path_...` 断言）；
拼接只有一处（`designText`）。
⑤ **装载未超预算**：≈13k tokens。

## 八、留给下游

- `DESIGN-03`：把 `registryAvailable` 从三态扩成四态并接真查询；本屏现在仍传 `null`（没查过）；
- 提交端点挂上之后，本屏**只改一个字符串**（`designSession.ts` 里那一处路径），
  流式与续跑两条不用动。
