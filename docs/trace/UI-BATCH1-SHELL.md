# UI-BATCH1-SHELL trace — 批次一（外壳与入口 4 屏）+ 五项裁决落地 + 两处清理 @2026-08-01

## 0 本轮范围

批次一 4 屏（S0 外壳 / P1 广场 / P2 工作台 / P3 combo）+ owner 五项裁决落地 + 两处清理。
`web/` 一字未动（63 测复跑全绿）；`contracts/` 与 `flint/domain/` 未动；后端端点响应形状未动；
零联网装包；零付费。

## 1 五项裁决落地

| 裁决 | 落点 | 状态 |
|---|---|---|
| ① `_ds` 的 ink-2 / rail 改值须明记 | **新建 `docs/设计系统-token偏离记录.md`**：3 处偏离逐条列新旧值 × 三种底的实算数字与原因；另记 spark 双值与 sulfur 两条纪律；末尾写明「改值必更表、NEVER 调松判据」 | 已落 |
| ② fact 字号缝须写下 | `components/honesty/channel-value.tsx:9-15` 文件头写死警告：解引用端点建成拿到**真数值**后，版式 MUST 反过来——**数值走大字号、id 继续小字**；现统一 12px 是「只有 id 可显」的正确解，**不是**「数字就该小」的结论 | 已落 |
| ③ 硫磺圈地（NEVER 进数据屏） | 不只写注释，**做成机器可验**：`scripts/check_contrast.py` 新增 `scan_sulfur_confinement()`，扫描前端源码，数据屏出现 `--sulfur` / `bg-cta-bg` / `text-cta-fg` 即失败；白名单只有营销屏 + token 定义处 + styleguide | 已落 · 已验非空转 |
| ④ 页脚未建条目整条不列 | `app/page.tsx` 的 `SITEMAP` 从 3 组 13 条（9 条标「未建」）缩为 1 组 4 条**全部真实可达**；渲染分支里的 `href === null` 整段删除，页脚底部那句「标未建的条目…」也删 | 已落 |
| ⑤ 费用估算器继续不并入 | 未并入，保持登记（无出处竞品价 + 比较广告风险 + 粉橙渐变挪用告警暖色族 + ¥1,299 报价而支付未建） | 保持 |

**③ 的防空转验证**（不是「跑了没报错」就算数）：把 `app/page.tsx` 移出白名单后重跑扫描，
确实抓到 2 条（`app/page.tsx:157` 的 `bg-cta-bg` 与 `text-cta-fg`）；白名单正确时为 0 条。
即这条门**会响**，不是摆设。

## 2 两处清理

1. **`start-demo.ps1` 加夹具自愈**：在 alembic 迁移之后、Pop-Location 之前插入
   `& $Py -m harness.demo_seed_report`，失败只 Warn 不中断（其余流程不受影响）。
   夹具被测试库清空过 4 次、每次报告屏变 404，加了就自愈。
   **编码实测**：改后 `start-demo.ps1` 仍为 UTF-8 **带 BOM**（脚本读字节确认 `b'\xef\xbb\xbf'`），
   中文未损。
2. **`app/deliverables/[id]/page.tsx` 过时注释**：原第 8 行写「视觉：实用暗色」+ 三个暗色 hex，
   双主题后已过时。改为「数据屏语言（日夜双主题，颜色全部走语义 token，本文件不写死任何颜色）」，
   并补两条圈地纪律（NEVER glow / NEVER sulfur）。

## 3 后端胶水：挂 `/categories`

- `harness/demo_server.py`：`from flint.api.app import create_app as create_categories_app`，
  `create_categories_app(DSN)` 并入 `include_router` 循环（`build_app()` 内）。
  **只挂既有 app，未改任何端点响应形状。**
- **实测有真数据**：`GET /categories` 回 **12** 条（`cat-ai / cat-robotics / cat-energy …`），
  故 S0 筛选用真目录，**未硬编码任何大类清单**。
- **`flint.api.pack` 刻意仍不挂**（owner 点名的坑）：它与 `deliverables` 都定义
  `GET /deliverables/{id}/render`，同挂会撞路由。挂载注释里写死了这条理由。
  **实测挂 categories 后 render 路由未受影响**：`fmt=markdown` → **409**、`fmt=pack` → **503**（既有正确行为）。

## 4 四屏

### S0 外壳 `components/shell/app-shell.tsx` + `components/shell/category-filter.tsx`

- wordmark + 导航（热点广场 / combo 入口 / 它怎么工作）+ 端点行（本屏读的真端点常驻可见）+
  大类筛选 + 用户位 + 主题切换。
- **用户位**：`X-User-Id` 取 `lib/api` 的真实常量（实测渲染为 `demo-user`），
  旁边明写「账户端点未建」。NEVER 画看起来能点的头像菜单。
- **大类筛选**：数据来自 `GET /categories`。**取不到就停用并标注**
  （「大类筛选不可用 · GET /categories 未返回目录（此处不代填清单）」），NEVER 拿写死清单顶上。
- **筛选仅隐藏行**：选中写进 `?cat=`，服务端按 `category_id` 过滤；
  rank 号取**后端原序位次**（过滤前先编号再过滤），隐藏后不重编号、不重排。

### P1 广场 `app/plaza/page.tsx`（重写）

- 由原「一簇一张大卡」改为**逐行表**（154 簇/日，卡片式不可用）：
  `# / 簇 CLUSTER / GTRENDS / WEIBO / GHTREND / ARXIV / HOTNESS 综合`。
- **四源各自独立一列**，NEVER 合成一个数、NEVER 堆叠图；缺源渲染
  「该源当日无数据」+ 虚线空心源印，**NEVER 补 0**（0 是「测到为零」，缺失是「当日没测到」）。
- 行可展开 → `hotness_components` 六个分量各自独立列出 + `total_heat`，NEVER 合成显示。
- **弱信号单列一轨**，与主榜分节，屏上明写「不并入综合分」。
- day 非法 → 后端 400，抬 `VALIDATION_FAILED` 并给「改查 2026-07-04」一条可点修正路径；
  前端 NEVER 预判日期格式。
- 空态（clusters 与 weak_signals 均空）→「该日无热点」，与「该大类下无主榜簇」是两句不同文案。
- 窄屏堆叠（同一份 DOM，每格自带列名），横向溢出实测 0。

### P2 工作台 `app/clusters/[id]/page.tsx`（新建）+ `components/honesty/flag-mark.tsx`（新建）

- **三种旗标各自可辨**，NEVER 合并成统一标签。每种三重区分（灰度下也分得开）：
  `novelty · 新奇`（星芒 + 实线边）/ `momentum · 动量`（箭头 + 双线底边）/ `revival · 复燃`（回环 + 虚线边）。
  颜色一律墨色——形状与边缘质地才是载体。
  **契约外的新旗标**：原样显示 + 点状边 + title 标注，NEVER 吞掉、NEVER 归并进已知三种。
- `top_links` 真实 `href` 可点（新窗口）；`keyword_ids` 逐条列出。
- **未知簇 = 空态非 404**：后端回 `evidence_cards: []`（HTTP 200），
  屏上「该簇暂无证据卡」并写明「未知簇也走这条路径——不是 404、不是错误」。实测 `/clusters/c-unknown-999` → **HTTP 200**。

### P3 combo `app/combo/new/page.tsx` + `components/combo/combo-composer.tsx`（新建）

- 跨簇选卡（来源 = 当日主榜前 8 个有卡的簇；**取多少是呈现范围的取舍，不是排序/筛选**，
  屏上写明「当日主榜共 154 簇，此处载入前 8 个有卡的簇」）。
- **卡数 2~5 且假设非空才可提交**，否则按钮 `disabled` 并写明还差什么（实测「还需选 2 张卡」）。
- **`degraded == true` → 明示「部分主题为降级生成（本地模型降级兜底），完整性可能低于正常水平」**，
  并注明这一位来自后端 `orchestrate_combo`、前端只据实标注。`false` 时也如实写一句。
  **这个字段此前全站没有任何屏能渲染，本批补上。**
- 400 / 422 / 网络断各自成屏，说清「发生了什么 / 怎么办」，**用户的选卡与假设保留不清空**。
- 提交中只说正在请求哪个端点，**不画百分比**（后端没有进度数据）。

## 5 验证（真实数字，全部本人跑）

| 项 | 结果 |
|---|---|
| `scripts/check_contrast.py`（含硫磺圈地扫描） | 两主题 × 22 对达标 + 圈地 0 违规，**exit 0** |
| 硫磺门防空转反证 | 白名单放开 → 抓到 **2 条**；白名单正确 → **0 条** |
| `npx tsc --noEmit` | **exit 0** |
| `node scripts/check-screens.mjs` | **71 / 71，exit 0**（本轮由 51 增至 71，新增 20 条批次一断言） |
| `node scripts/check-connectivity.mjs` | **94 / 94，exit 0** |
| `ui_probe`（3 新屏 × 2 主题 × 桌面/移动 = 12 张） | **问题计数 0**（横向溢出 / 控制台 error / 打不开） |
| `ruff check .` | All checks passed |
| `mypy --strict flint` | 224 文件净（另单测 `harness/demo_server.py` 净） |
| `pytest -q` | **1 failed, 1337 passed**（唯一红为既存基线 `test_m4_023.py:64` 计数 232 vs 218，**failed 数未增**） |
| `cd web; npm test -- --run` | **11 文件 / 63 测全绿**（一字未动） |

**新增断言里最要紧的三条**（不是形式断言，是把铁律钉死）：
- `P1 主榜序与后端逐一致` — 把页面上出现的 `cluster_id` 次序与 `GET /plaza/hot` 返回次序**逐一比对**，
  实测 154 簇完全一致 → 证明前端零重排。
- `P1 筛选仅隐藏行、次序不变` — 过滤后的次序须是后端序列的**子序列**，实测一致。
- `P2 未知簇 HTTP 200（不是 404）` — 直接断言状态码。

## 6 我真看过的截图 / 没验证的

**真看过（逐张 Read）**：
- P2 工作台 日间桌面（S0 外壳、12 个真大类、`X-User-Id demo-user · 账户端点未建`、
  1 张真卡带 novelty 旗标与可点微博外链）
- P1 广场 夜间桌面（`?cat=cat-quantum` 过滤态：0 行时的两句文案、表头、弱信号轨）
- P1 广场 日间桌面（`?day=2026-07-05`，106 行全表：序号、四源独立列、大量「该源当日无数据」、
  hotness 降序、底部弱信号轨）
- P3 combo 日间桌面（跨簇选卡、选卡篮 0/5、假设框、`还需选 2 张卡`、提交按钮置灰）
- P3 combo 夜间移动（堆叠正确、chips 换行、无溢出）

**没验证（不背书）**：
- **`degraded == true` 的屏没见过**。我真跑了一次 `POST /projects/combo`（免费本地 qwen，
  HTTP 200 / 24.2s / 6 个 topic_ids），但**回的是 `degraded: false`**——
  true 分支只有后端生成降级时才出现，我无法诚实地伪造它。故：
  **false 分支已实机验证，true 分支代码在场但未被执行过。**
- P1 广场**日间/夜间移动端**与 P2 **夜间**我只有探针的「0 溢出」量测，**没有逐张看图**
  （只看了上面列出的 5 张）。
- 提交交互（选卡 → 点提交 → 成功屏）**未在浏览器里点过**——探针只读不点。
  成功屏的字段渲染是照 200 响应的真实形状写的，但**那一屏我没看过**。
- `next build` 生产构建未跑；平板断点未测；`prefers-reduced-motion` 未实机验。

## 7 给 owner 的观察（不代拍）

1. **demo 日的 154 个簇全部是 `cat-ai`**（实测 `cat-ai` 命中 154 / 154）。
   所以大类筛选在当前数据下近乎二值：选 `cat-ai` 出全部，选其它 11 类都出 0 行。
   筛选逻辑本身已验（次序不变），但**「隐藏部分行后 rank 不连续」这个特性没有真实数据能演示**。
2. **hotness 是全精度浮点**：实测 `87.74727606639746` / `8.37934425029087`，
   17 位有效数字，把 HOTNESS 列撑得很宽。我**按原样显示、没有四舍五入**——
   舍入属前端加工，要不要为显示截断由你定。
3. **同日 106 个簇只有 10 个不同的 hotness 取值**（大量并列）。
   排名在并列组内实际由后端返回序决定，不是真实区分度。
   这指向 hotness 参数仍是初值（S4 未标定），不是前端问题。
4. **P3 选卡来源只载入前 8 个有卡的簇**。这是我为避免一次拉 154 簇证据卡做的呈现取舍，
   屏上已写明。若你要全量可选，需要一个「按簇搜索/分页选卡」的交互，那是另一张卡。

## 8 落盘清单

| 文件 | 改动 |
|---|---|
| `docs/设计系统-token偏离记录.md` | **新建**（裁决 ①） |
| `start-demo.ps1` | 加夹具自愈（UTF-8+BOM 保持） |
| `harness/demo_server.py` | 挂 `/categories`；挂载注释写明 pack 为何 NEVER 挂 |
| `V0 files 前端设计/lib/types.ts` | 新增 `Category` |
| `V0 files 前端设计/lib/api/categories.ts` | **新建** |
| `V0 files 前端设计/lib/api/index.ts` | 导出 `fetchCategories` |
| `V0 files 前端设计/components/shell/app-shell.tsx` | **新建**（S0） |
| `V0 files 前端设计/components/shell/category-filter.tsx` | **新建**（仅隐藏不重排） |
| `V0 files 前端设计/app/plaza/page.tsx` | **重写**（P1 表式主榜 + 弱信号轨 + 400 屏） |
| `V0 files 前端设计/app/clusters/[id]/page.tsx` | **新建**（P2） |
| `V0 files 前端设计/components/honesty/flag-mark.tsx` | **新建**（三旗标各自可辨） |
| `V0 files 前端设计/app/combo/new/page.tsx` | **新建**（P3 服务端） |
| `V0 files 前端设计/components/combo/combo-composer.tsx` | **新建**（P3 交互 + degraded） |
| `V0 files 前端设计/app/page.tsx` | 页脚未建条目整条移除（裁决 ④） |
| `V0 files 前端设计/app/deliverables/[id]/page.tsx` | 过时注释更新（清理 2） |
| `V0 files 前端设计/components/honesty/channel-value.tsx` | 补裁决 ② 的缝注释 |
| `V0 files 前端设计/scripts/check-screens.mjs` | 新增批次一 20 条断言 |
| `scripts/check_contrast.py` | 新增硫磺圈地扫描（裁决 ③） |

**未动**：`contracts/`、`flint/domain/`、任何后端端点响应形状、`web/`、`components/ui/**`、`lib/mock/**`、`flint/api/**`。
