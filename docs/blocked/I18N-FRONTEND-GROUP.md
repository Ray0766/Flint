# blocked · I18N 前端组（I18N-02/04/05/06/07/08）—— 与 I18N-01 同两个未决

**状态** closed · 2026-08-05 · `HYG-01`

## 卡与其前端产出

| 卡 | 前端产出（卡上路径） | 后端半边 |
|---|---|---|
| I18N-02 | `web/src/messages/{zh,en}.json` + `tools/i18n_scan.mjs` | 无 |
| I18N-04 | `web/src/components/native-name/` | `flint/i18n/name_display_job.py`（可做） |
| I18N-05 | `web/src/components/quote-slot/` | 无 |
| I18N-06 | `web/src/stores/prefs.ts` | `flint/profile/prefs.py`（可做） |
| I18N-07 | `tools/orthogonality_check.py` | 依赖 I18N-01/06 |
| I18N-08 | `web/src/components/region-switch/` | 无 |

## 两个未决（与 `docs/blocked/I18N-01.md` 同源）

1. **`web/` 路径口径**：卡里一律写 `web/src/…`，**实仓 `web/` 下是 `app/ components/ lib/`，没有 `src/`**。
   DEC-003 做 `src/`→`flint/` 重映射时，把 **153 处前端路径按上下文跳过了**——
   那是「不误伤」，不是「已对齐」。现在轮到前端卡，这笔账必须先结。
2. **next-intl 未装**（I18N-01），而 I18N-02 的 key 化、I18N-04/05/08 的组件都建立在它之上；
   装它需要真实网络 = §7 事前必审，NEVER 自行触碰。

## 为什么不「先做后端半边」

I18N-04 与 I18N-06 的 `verify_cmd` 是 **`pytest … && cd web && npm test …`** 的**合取**：
后端半边写完也过不了卡的验收命令。按 §4.2「测试必须覆盖 acceptance 语义」，
只交后端半边并记 verified 是**把没做完的说成做完了**。
故整卡 blocked，后端半边留待口径落定后连同前端一次收。

## 需要 owner 的两句话

1. 前端路径：**按实仓为准，把 tasks-v04.json 里 `web/src/` 统一重映射为 `web/`**（推荐，与 DEC-003 同法）；
   或指示在 `web/` 下新建 `src/` 并迁移既有 `app/ components/ lib/`（那是前端结构调整，影响面大得多）。
2. 依赖：放行一次 `npm install next-intl`（含 RegistryValidator 校验 + 锁版），或指定离线方案。

## 绕行现状

V2 的 REGION 组八张全部 verified；I18N 组仅 I18N-03（纯后端）verified，
其余六张 blocked。**不受影响的 V3/V4/V5 纯后端卡（HOTSPOT-08 / FAV-01 / GRAPH-02 / DESIGN-30）
依赖已就绪**，下一会话可直接接力。

## 关闭（HYG-01 · 2026-08-05）· 根因逐条实跑，NEVER 凭印象

**① 依赖已在栈里**（这张单的根因原话：「实测 `web/package.json` 里**没有** next-intl」）：

```
$ grep -n "next-intl" web/package.json
15:    "next-intl": "4.13.4",
```

**② 那 13 张 I18N 卡在 `docs/progress-v04.jsonl` 里全部 `verified`**：

```
I18N-01 verified   I18N-02 verified   I18N-03 verified   I18N-04 verified
I18N-04-a verified I18N-04-b verified I18N-05 verified   I18N-06 verified
I18N-06-a verified I18N-06-b verified I18N-07 verified   I18N-08 verified
I18N-09 verified                                          合计 13 张
```

**③ 前端产出逐个在盘上**：`web/messages` · `web/components/native-name` ·
`web/components/quote-slot` · `web/stores/prefs.ts` · `web/components/region-switch` ·
`tools/orthogonality_check.py` · `tools/i18n_scan.mjs` —— 七项全在。

**这张单当时的问题（要真实网络装依赖，属事前必审）已经由 owner 走过**：
依赖在 `web/package.json` 里锁着版本号。单子留档，状态转 closed。
