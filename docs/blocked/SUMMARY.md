
**状态** historical · 2026-08-02 · 历史留存
> ## ⚠ 历史留存 —— 这不是当前状态
>
> 本单记的是**当时**的状况，已不再更新。
> **NEVER 把它当作当前状态引用**：当前状态看 `docs/progress-v041.jsonl` 的尾部
> 与各单顶部那行 `**状态**`。
> 照着一份过期的地图走，而地图上没有一个字说它过期了——那是这条横幅要挡的事。

> **【2026-08-03 追记】本文件是 2026-08-02 那次停机（§7 条件②）的历史留存。**
> 两个 blocked 根因已由 owner 的 DEC-006/007 裁决消除，104 张卡现已全部 verified；
> 当前状态见 `docs/V04-COMPLETION.md`。**NEVER 把本文件的进度表当作当前状态引用。**

# v0.4 增量 · 停机汇总（worker.md §7 停机条件 ②）

**停机时间** 2026-08-02
**停机依据**：§7「剩余卡**全部 blocked** 且**无依赖就绪卡**可做」——实测就绪卡 = **0**，
58 张未完成卡**逐张可追溯**到两个 blocked 根因（追不到根因的为 0 张）。

## 一、进度

| 里程碑 | verified | blocked | 说明 |
|---|---|---|---|
| V0 原则与返工 | **9/9** | 0 | SELFCHECK-V0 已过 |
| V1 Schema | **15/15** | 0 | SELFCHECK-V1 已过 |
| V2 地区+语言 | 9/16 | 7 | REGION 组 8 张全绿 + I18N-03；I18N 前端 7 张 blocked |
| V3 广场+收藏+分享 | 2/15 | 0 | FAV-01、HOTSPOT-08（纯后端部分） |
| V4 图谱工作台 | 2/16 | 0 | GRAPH-02、GRAPH-14 |
| V5 设计工作台 | 1/32 | 0 | DESIGN-30 |
| **合计** | **42/103** | 7 | — |

**全局门（停机时实测）**：`ruff check --no-cache .` All checks passed ·
`mypy --strict flint` **246 文件净** · `pytest -q` **1605 passed / 0 failed**。
冻结件零改动：`contracts/models.py` md5 `380d7b5a7dae…`、`protocols.py` `eb19b73e176e…`。

## 二、两个阻塞根因（**只需 owner 两句话**）

| 根因 | 直接卡住 | 传递卡住 | 需要什么 |
|---|---|---|---|
| **I18N-01** next-intl 未装 | I18N-02 | **33 张** | 放行一次 `npm install next-intl`（含 RegistryValidator 校验 + 锁版）。这是 §7「真实网络启用」= 事前必审四项之一，**NEVER 授权给我**。 |
| **I18N-04** 前端路径口径 | I18N-05/06/07/08 | **28 张** | 定 `web/` 路径口径：卡里一律写 `web/src/…`，**实仓 `web/` 下是 `app/ components/ lib/`，没有 `src/`**。建议按 DEC-003 同法**以实仓为准**，把 tasks-v04.json 里前端 `web/src/` 统一重映射为 `web/`。 |

两处细节见 `docs/blocked/I18N-01.md` 与 `docs/blocked/I18N-FRONTEND-GROUP.md`。

**为什么不先做后端半边**：I18N-04/06 的 `verify_cmd` 是
`pytest … && cd web && npm test …` 的**合取**——后端写完也过不了卡的验收命令。
只交半边并记 verified，就是把没做完的说成做完了（§4.2）。

## 三、其余未清 blocked（非阻塞，等 owner 一句话即可关）

| 单 | 内容 |
|---|---|
| `SCHEMA-05-FROZEN-WORDING.md` | acceptance 写「frozen 拒二次赋值」，真件 `Cluster` 非 frozen；已按 contracts/ 实现**字段级写一次**。请对齐措辞。 |
| `REGION-06-AXIS-WORDING.md` | acceptance 写「authority 轴接 `EvidenceScore.axis`」，而 `EvidenceOrigin` 只有两值；已记入 `components`。请对齐措辞。 |
| `CLAUDE-S3-LAG.md` | CLAUDE.md S3 目录结构仍是包模板形态（owner 明令本体零修改）。 |
| `CONCURRENT-WORKER-COLLISION.md` | 已按方案 A 处置完毕，可标记关闭。 |

## 四、DEC 编号

已用到 **DEC-005**（DEC-000 连跑授权 / DEC-001 §3 边界 / DEC-002 worker.md 落点 /
DEC-003 `src/`→`flint/` / DEC-004 contracts_v04 ruff 豁免 / DEC-005 `flint/grounding.py` 转包）。
下一位从 **DEC-006** 起。

## 五、解阻后的接力顺序

owner 给出上面两句话之后，就绪卡会立刻回到 I18N-01 → I18N-02 → I18N-04/05/06 → I18N-07/08，
V2 出口 SELFCHECK-V2 随即可跑；V3/V4/V5 的其余 55 张卡在 V2 通畅后按 DAG 自然解锁。

---

## 六、第二次停机（同一根因，追加 §4.5 拆卡后的结果）

owner 指令「继续」后，我撤了 `FLINT-V04-DONE` 标记并按 **§4.5 拆卡**再推进了一轮：

| 拆分 | -a（后端，**已 verified**） | -b（前端，仍 blocked） |
|---|---|---|
| I18N-04 | `flint/i18n/name_display_job.py` —— 主行 == native 字节等同 + translate 作业走既有 JobRunner（H7） | native-name 次要行组件 —— 次要行带机翻标记 |
| I18N-06 | `flint/profile/prefs.py` —— 服务端为真相 + 跨设备一致 | `stores/prefs.ts` —— 无 localStorage 读写源码断言 |

**拆分 NEVER 改变原卡 acceptance 总集**：两条 acceptance 各归一半，无遗漏无新增。

进度更新：**44/103 verified**（+I18N-04-a、I18N-06-a），blocked 仍 7 张（原卡）。
`pytest -q` **1626 passed / 0 failed** · ruff 净 · mypy **248 文件净**。

### 为什么仍然停机

再次实测：**就绪卡 = 0**。剩余 58 张里只有 13 张是纯 pytest 卡，
而它们的链条**根部全是前端卡**：

```
HOTSPOT-03 缺 HOTSPOT-01（cd web && npm test）
HOTSPOT-04 缺 HOTSPOT-03 → 05 → 06 → {FAV-02, DESIGN-25}
DESIGN-28  缺 DESIGN-02（cd web && npm test）→ DESIGN-29 / 32
DESIGN-16  缺 GRAPH-08（cd web && npm test）
```

也就是说：**能拆的已经拆完，剩下的纯后端卡都被前端根部卡住**。
继续拆下去就要去拆那些**本身就是纯前端**的卡（HOTSPOT-01 / GRAPH-01 / DESIGN-02…），
那不是拆分，是把「做不了」写成「做完了」。

**两个根因未变，仍只需 owner 两句话**（见 §二）。
