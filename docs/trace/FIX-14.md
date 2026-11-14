# FIX-14 · 卡号跨批次唯一（以及撞车之后该怎么办）

> v0.4.1 第 6 批第十五张。全量 `pytest -q` **4509 passed / 0 failed**。

## 装载清单

`tasks-v041-b6.json#FIX-14` · `docs/blocked/CARD-ID-COLLISION-DESIGN-01.md` ·
七份任务表（`tasks-v04.json` + `docs/steward/tasks-*.json`）·
`tools/check_outputs_declared.py` · `docs/progress-v041.jsonl`（append-only 那条纪律）。
约 10k tokens，**未超 40k**。

## 一、单子记了一张，实际是**四**张

开工第一件事是把七份任务表并起来数（277 个卡号）：

| 卡号 | v0.4 | v0.4.1 |
|---|---|---|
| `DESIGN-01` | 对话面板 + SSE 流式渲染 | `design_generate` 的消费者（b5） |
| `DESIGN-02` | 渲染管线 `iframe.srcdoc` | 设计台那一屏（b5） |
| `DESIGN-03` | 三接口抽象 | 固化为模板 + 第四态（b5） |
| `REGION-08` | `by_source` 跨国分列 | `clusters` 加 region 列 · 迁移 0021（**本批**） |

**四张两侧的 outputs 完全不同。** 单子只点了一张——
这也是为什么它拖到现在才被数清。

## 二、处置：一个号都不改。卡面那句话已经不成立了

卡面写的是「改新的那张更安全——旧卡已 verified」。**开工时对，现在不对**：
四张新的也全部 verified 了（`DESIGN-01/02/03` 是第 5 批，`REGION-08` 是本批）。

改任何一侧的号，代价是同一种：

- `docs/progress-v041.jsonl` **append-only**，那些 `started`/`verified` 事件
  会指向一个不存在的卡号——**指错的引用与指对的长得一模一样**；
- 台账配对尺子当场报「未配对事件」，而那句话读起来像「有张卡被丢了」；
- `docs/trace/REGION-09.md`、`docs/trace/REGION-10.md` 逐字引着 `REGION-08`。

**所以改号现在是有害的。** 这一处与卡面写的处置不同，
理由逐条写进了 trace 与单据——**偏离要说出来，NEVER 默默照做或默默不做**。

## 三、真正的修法（两条）

1. **跨批次唯一性判据**：冻结闭集之外出现任何重复即红并**点名两处出处**。
   闭集四条各写明两侧是什么，**NEVER 增补**——新的撞车应当被抓红而非入册。
   另有一条钉住「闭集与实况逐条对得上」：多一条会**替下一次真撞车打掩护**；
2. **`check_outputs_declared.py` 歧义即抛**（`AmbiguousCardId`）。
   这才是那次误判的直接修法——它把这四张撞车的**实际危害清零**。

## 四、那道拒绝的位置，两次调整

**第一版放在同包兄弟豁免之前**，尺子当场崩了：
`flint/design/__init__.py` 的首行只提了一个卡号区间（「DESIGN-01~32」），
它本该被那条既有规则豁免掉。**顺序错了的尺子与真有病长得一模一样**——
它报的是 `AmbiguousCardId`，而真相是我把检查插早了。

**第二版对不在任何表里的卡号抛了 `KeyError`**，把 `test_outputs_declared`
自己构造的合成卡（`X-99`）打红了。改成回 `None`：
那不是歧义，是「这个卡号没有卡」——那件事由 C 类自己去报（它报得更准，
还带上是哪个文件自述的）。在那里抛的话，一次「卡号打错了」会以 `KeyError` 收场，
**读起来像尺子崩了**。

## 五、verify

```
pytest tests/v041/test_card_id_unique.py -q      → 9 passed
pytest tests/v041/test_outputs_declared.py -q    → 全绿（合成卡不再被误伤）
python tools/check_outputs_declared.py           → 三类差异只剩白名单里的历史条目
pytest -q（全量）                                 → **4509 passed / 0 failed**
ruff / mypy --strict flint / check_line_endings  → 全绿 / 306 files / 220 LF
```

## 六、self_review

① 判据覆盖 acceptance 五条，含**两条阴性对照**（注入一张重号必抓 /
无歧义时照常返回，NEVER 一律抛——「更严格」与「不能用」是两件事）
与一条守扫描面（少读一份表会让判据因「没看见」而绿）；
② 零冻结件改动；③ 无禁用词；
④ 改动面：`tools/check_outputs_declared.py` + 判据 + 单据，
**全在卡上 outputs**（`tools/` · `docs/steward/` · 测试）。
`docs/steward/` 本卡**没动**——因为处置是「不改号」；
⑤ 装载 ≈10k tokens。

## 七、留给下游

**新卡号在开卡时就要跨批次查重**——那条判据现在会替你查。
`tasks-v041-b7.json` 若再出现与旧表重号的卡，`pytest -q` 当场红并点名两处出处。
