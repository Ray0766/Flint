# 卡号撞车：`DESIGN-01` 在 v0.4 与 v0.4.1 第 5 批各是一张不同的卡

**状态** closed @2026-08-09 · `FIX-14`（v0.4.1 第 6 批）

> 发现者：worker，v0.4.1 第 5 批 `DESIGN-01` 执行中（跑全局门时被 `check_outputs_declared` 报出来）。

## 现象

同一个卡号 `DESIGN-01`，两张卡：

| 出处 | 标题 | outputs |
|---|---|---|
| `tasks-v04.json` | 对话面板 + SSE 流式渲染（P3 上线：delta 入 replay + 截断补发） | `web/design/chat-panel/` · `flint/design/session.py` · `tests/v04/design/test_stream_events.py` |
| `docs/steward/tasks-v041-b5.json` | 工作台①：`design_generate` 没有消费者 | `flint/jobs/` · `tests/v041/test_design_generate_job.py` |

## 它已经害了一次

`tools/check_outputs_declared.py` 的 C 类规则按**模块 docstring 首行的卡号**去查那张卡的
`outputs`。新建的 `flint/jobs/design_generate.py` 首行若写 `DESIGN-01：…`，
对账器会拿 **v0.4 那张卡**的 outputs 来判它，于是报：

```
C flint/jobs/design_generate.py DESIGN-01 docstring 自述 DESIGN-01，却不在任何卡的 outputs 里
```

**那句话是假的**——它在自己那张卡（第 5 批的 `DESIGN-01`）的 `outputs`（`flint/jobs/`）里写着。
假的红与真的红一样会逼人做事，而这次要做的事是「去改一个没错的东西」。

## 绕行现状

新模块的 docstring **首行不写那个卡号**，改在正文里写明「由 v0.4.1 第 5 批的 `DESIGN-01` 建」
并说清为什么不写在首行。对账器的房规原话是
「正文里提到别的卡号是**引用**，不是自述」——这正是引用。

**没有动 `LEGACY_UNDECLARED`**：那张表的文档写死「冻结闭集，NEVER 增补新条目——
新的少声明应当被抓红而不是入册」，而本条根本不是少声明。
**也没有扩大对账器的读取面**：让它一并读 `docs/steward/tasks-v041-b*.json` 试过，
会翻出三条**跨批的旧账**（`flint/region/legal_policy.py`/`legal_probe.py` 自述 K2-01、
`flint/topic/cards_context.py` 自述 BL-02，三者都不在各自卡的 outputs 里）——
那是别的批次的事，不该由这张卡顺手改掉。

## 需要 owner / steward 的什么

1. **卡号该不该跨批唯一**？今天不唯一。若定为唯一，第 5 批的 `DESIGN-01` 要改号
   （台账、trace、工单三处一起改）；
2. **对账器要不要认识 v0.4.1 的卡**？要的话，顺带会暴露上面那三条跨批旧账，
   请一并裁决怎么处理（修 outputs 声明 / 入册并写理由 / 改 docstring）。

在两条都没定之前，本模块按「首行不写歧义卡号」交付，行为与判据都不受影响。

---

## 结案（`FIX-14` · v0.4.1 第 6 批）

### 一、本单只记了一张，实际是**四**张

开工第一件事是把全部任务表并起来数（7 份表 / 277 个卡号）：

| 卡号 | v0.4 那张是什么 | v0.4.1 那张是什么 |
|---|---|---|
| `DESIGN-01` | 对话面板 + SSE 流式渲染 | `design_generate` 的消费者（b5） |
| `DESIGN-02` | 渲染管线 `iframe.srcdoc` | 设计台那一屏（b5） |
| `DESIGN-03` | 三接口抽象 | 固化为模板 + 第四态（b5） |
| `REGION-08` | `by_source` 跨国分列 | `clusters` 加 region 列 · 迁移 0021（b6） |

**四张两侧的 outputs 完全不同。**

### 二、处置：**一个号都不改**——卡面那句话已经不成立了

卡面写的是「改新的那张更安全——旧卡已 verified」。**开工时对，现在不对**：
`DESIGN-01/02/03` 是第 5 批的卡、`REGION-08` 是本批的卡，
**四张新的也全部 verified 了**。

改任何一侧的号，代价是同一种：

- `docs/progress-v041.jsonl` 是 **append-only**，那些 `started`/`verified`
  事件会指向一个不存在的卡号——**指错的引用与指对的长得一模一样**；
- 台账配对尺子会当场报「未配对事件」，而那句话读起来像「有张卡被丢了」；
- `docs/trace/REGION-09.md`、`docs/trace/REGION-10.md` 里逐字引着 `REGION-08`。

**所以改号现在是有害的。** 本卡改的是别的两样。

### 三、真正的修法（两条）

1. **跨批次唯一性判据**（`tests/v041/test_card_id_unique.py`）：
   冻结闭集之外出现任何重复即红，并**点名两处出处**。
   闭集四条各写明两侧是什么，**NEVER 增补**——新的撞车应当被抓红而非入册；
   另有一条判据钉住「闭集与实况逐条对得上」（多一条会替下一次真撞车打掩护）。
2. **`check_outputs_declared.py` 歧义即抛**（`AmbiguousCardId`）：
   这才是那次误判的直接修法——它把这四张撞车的**实际危害清零**。

### 四、那道拒绝的位置很讲究

它放在**同包兄弟豁免之后**。放更早的话，`flint/design/__init__.py`
（首行只提了一个卡号区间「DESIGN-01~32」）会先被拦下——
而它本来就该被那条规则豁免掉。**顺序错了的尺子与真有病长得一模一样。**

另：卡号**不在任何表里**时回 `None` 而不是抛——那不是歧义，是「这个卡号没有卡」，
那件事由 C 类自己去报（它报得更准，还带上是哪个文件自述的）。
在那里抛的话，一次「卡号打错了」会以 `KeyError` 收场，读起来像尺子崩了。

### 五、给下一批的一句话

**新卡号在开卡时就要跨批次查重**——那条判据现在会替你查。
`tasks-v041-b7.json` 若再出现一个 `DESIGN-04` 之类与旧表重号的，`pytest -q` 当场红。
