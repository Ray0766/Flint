# REDESIGN-03 · 继续细化：工作台、空态、模板工具、干预页、手机回看（@2026-11-14）

接 `REDESIGN-02`。owner 的话没有变：「方向对，继续细化」。
这一卡除了样式，还改了两处**屏上说错话或什么都没说**的地方（演示串屏、干预页），那两处判据先行。

## 一、装载清单

`docs/trace/REDESIGN-02.md` §六（没做的屏）· `web/app/redesign.css` · `web/app/globals.css` 的
`.design__*`、`.intervention-*`、`.workbench__*` 三段 · `web/components/DemoFlow.tsx` ·
`web/components/design-workbench/DesignWorkbench.tsx` · `web/app/deliverables/[id]/interventions/page.tsx` ·
`web/components/BlockInterventionPanel.tsx` · `web/lib/i18n/enumLabel.ts` · `contracts/models.py#BlockType`
· `tests/v041/test_enum_labels.py`。真栈上各屏的 DOM 是在浏览器里逐屏取的。

## 二、改了什么

| 屏 | 改前（`REDESIGN-02` 之后） | 改后 |
|---|---|---|
| 计划书工作台 | 右栏章节导航宽 138px，一句检查项折成三四行；画布里「还没有生成任何内容」是左上角一行字 | 导航 224px，每章一行条目、之间一条细线；那句话是画布中间的一块空态 |
| 正文区只有一句话的屏（没有这张工作台、执行包与质量卡接口未提供） | 左上角一句话 | 一条通用规则：正文区唯一的子节点是一段字或一枚「未提供」标，就放到中间成一块 |
| 演示串屏 | 进屏就印「该区当日无数据」——其实是**还没取过数**；加载键是一枚灰色默认按钮 | 没取过数时印「还没加载。点上面的按钮取这一天的热点。」；取过之后才有「有」与「没有」之分；加载键是主按钮 |
| 模板工具 | 五块竖着排满 1592px，预览区空着两百像素，固化键悬在半空 | 宽屏两栏：左边输入与生成过程，右边预览与固化；预览区是一块卡，空态居中 |
| 干预页 | 带引用的段落、表格、图表、质量卡、引用列表、缺口提示这六类块**没有任何内容**，只有「锁定 / 再生成 / 一个没有名字的输入框 / 争议」 | 每行先印块类型标签，再印这一块自己文字的开头；输入框有名字与提示语；动作排成一条 |
| 导出页 | 五行「格式 + 键」贴在左上角 | 一张卡，每行格式在左、键在右 |

### 标记与逻辑上的改动（其余全是样式）

1. `DemoFlow.tsx`：多一个 `plazaLoaded` 状态。没取过数时渲染 `[data-demo-not-loaded]`，不渲染 `PlazaCards`；
2. `lib/blockExcerpt.ts`（新）：一块的摘要。标题与声明给原文；段落把开头连续的文字 span 接起来，
   遇到第一个没有文字的 span 就停并加省略号；表格给表头；其余四类块返回空串。
   **只截断，不改写**——跳过引用把后文接上来，得到的是一句原文里不存在的话；
3. 干预页用它，并在每行加 `.intervention-row__kind[data-block-type]`，屏上印 `enumLabel("block_type", …)`；
4. `enumLabel.ts` 加 `block_type` 一族（八个成员，真相源 `contracts.models::BlockType`），中英文案各八条；
5. `BlockInterventionPanel.tsx`：争议理由的输入框加 `aria-label` 与 `placeholder`（两条新文案）。

封版的那棵块树（`DEC-021`）一个节点没动。

## 三、判据（先写，先红）

| 判据 | 改前 | 改后 |
|---|---|---|
| `web/components/DemoFlow.test.tsx` 新增两条（没取过数不说「无数据」；取过且为空才说） | `1 failed | 2 passed` | 3 passed |
| `web/lib/blockExcerpt.test.ts`（6 条） | 模块不存在，整份红 | 6 passed |
| `web/__tests__/app/interventions_rows.test.tsx`（4 条） | `3 failed | 1 passed`（过的那条是「受保护的块照旧没有动作键」，本来就该过，留作对照） | 4 passed |
| `tests/v041/test_enum_labels.py` 的对齐表加一行 `block_type ↔ BlockType` | — | 过 |

干预页那份测试第一次跑是四条全红，原因是我把取数状态写成了 `kind: "ok"`（实际是 `"ready"`），
页面根本没渲染出行——那是夹具错，不是判据在工作。改对夹具之后才是上表的 3 红 1 绿。

样式那一半没有新判据，理由同 `UIR-01` §四；`tests/v041/test_redesign_layer.py` 的 11 条继续守着这一层。

### 五条门

| 门 | 结果 |
|---|---|
| `npx tsc --noEmit` | 零条 |
| `npx vitest run` | 88 份 / 887 条全过（上一卡 86 份 / 875 条） |
| `ruff check .` | 零条 |
| `mypy --strict flint eval harness` | 371 份零条 |
| `pytest -q` | 整套跑了一遍：`2 failed, 5410 passed, 458 skipped`（301 秒） |

红的两条是 `tests/v041/test_gauge_map_b2.py` 的「落盘副本过期」：新加的
`interventions_rows.test.tsx` 被清点器挂到了一条 acceptance 上，落盘的清点表里没有它。
按报错里写的命令重生成（`python tools/gauge_map.py --batch b2`），差异是 json 里多四行。
重生成之后**没有再跑整套**，只复跑了相关的五份（`test_gauge_map_b2`、`test_enum_labels`、
`test_redesign_layer`、`test_i18n_keys_defined`、`test_generated_artifacts_lf`）：`58 passed, 3 skipped`。

清点器在 macOS 上写出的是 LF，而仓里这两份（json 与清点报告）是 Windows 上生成的 CRLF。
直接提交会是两万行的差异。我按仓里原有的换行写回，差异就是那四行。
清点器自己不指定换行这件事没有修（`tools/gauge_map.py:447-448`），与 `MAC-07` 治的是同一种病。

## 四、验证（真浏览器，真栈）

| 屏 | 1920×1080 | 390×844 | 暗色 |
|---|---|---|---|
| 计划书工作台 | 看过 | `scrollWidth == 390`；章节栏宽 332（画布 356 减内边距），占满 | 看过（1920） |
| 演示串屏 | 进屏：`[data-demo-not-loaded]` 在、`[data-plaza-empty]` 不在；键的底色 `rgb(255, 122, 51)` | 点加载后 159 张卡、提示消失、`scrollWidth == 390` | 没看 |
| 模板工具 | 两栏，看过 | 一栏，`scrollWidth == 375`（375×812 下量的） | 没看 |
| 干预页 | 九行各有类型标签；有文字的五行有摘要；六个输入框都有提示语 | `scrollWidth == 390`；输入框高 64、内容高 62，提示语不被裁 | 没看 |
| 导出页 | 看过 | `scrollWidth == 375`（375×812 下量的） | 没看 |
| 收藏（空态） | 看过，没有要改的 | 没重看 | 没看 |
| 热点分析、作业屏 | — | — | 看过（1920），补上 `REDESIGN-02` 欠的两格 |

截图在 `.run/uir/redesign3-*.jpg`（六张，本机）。

### 手机回看时抓到的三处（都修了）

1. 章节栏加宽到 224px 的那条规则压过了旧表「窄屏占满一行」，手机上章节栏只占左半边。补了窄屏覆盖；
2. 底栏当前项「计划书工作台」六个字 60px，比一格 56px 宽，右半截被下一格的底色盖住。
   当前项叠到邻格之上；改后量到标签 60px、`scrollWidth` 也是 60，整句露出来；
3. 干预页输入框的提示语在一行高的框里折成两行、被裁掉一半。窄屏下框给到两行高。

## 五、装饰性决定（我定的，可推翻）

- 两条新文案的措辞：「还没加载。点上面的按钮取这一天的热点。」「写下你不认这一块的理由，再点「争议」。」；
- 八个块类型的中文标签：标题、段落、表格、图表、声明、质量卡、引用列表、缺口提示；
- 模板工具左栏宽 `minmax(360px, 30em)`；干预页受保护那句话从虚线标改成一句普通说明。

## 六、顺带看到的（没动）

1. **模板工具的「固化为模板」在没有产物时也点得动。** 这是有意的（`web/app/design/page.tsx:115-120`
   的注释：送空串，端点照实拒）。我没有改这个行为，只把它记在这里：屏上一枚亮着的主按钮、
   点下去必被拒，观感上像个缺陷；
2. 干预页的图表、质量卡、引用列表、缺口提示四类块只有类型标签、没有内容。它们的内容要解引用
   （图表数据、卡片、引用条目），这一屏今天不取那些；同一份报告里有两张图表时，两行会长得一样；
3. 开发模式下左下角那枚圆形「N」是 Next.js 的开发指示器，手机视口下盖住底栏第一格。生产构建里没有它。

## 七、没有做的

- `/topics/[id]`、`/workbenches/[id]` 有内容时的样子、`/share/[token]`、主题列表：没有逐屏细化
  （前两屏要真调模型才有内容）；
- 暗色下的演示串屏、模板工具、干预页、导出页没看；
- `globals.css` 里旧设计留下的死规则没有清；
- `tools/gauge_map.py` 写文件不指定换行，在 macOS 上重生成会把整份改成 LF（见 §三）；
- 80 条读 `.ui-probe/` 的取证判据仍在量旧外壳（全部 skip，问题单开着）。
