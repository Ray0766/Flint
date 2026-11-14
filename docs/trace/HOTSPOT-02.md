# HOTSPOT-02 trace — 卡片三独立动作 + 点击排除区 @2026-08-03

## 1 verify
`cd web && npm test -- --run components/hotspot-card-actions` → **6 passed**；
typecheck 干净；`i18n_scan` exit 0；前端全套 140 passed / 23 files。

## 2 为什么必须有点击排除区
卡片整体可点（跳详情），动作区在卡片**内部**。不停止冒泡的话，
用户点「收藏」会**同时跳走**——收藏成没成他都看不见。

## 3 双断言（acceptance）
| 断言 | 测试 |
|---|---|
| 三 handler **独立**触发 | 三条各一：点收藏时另两个 `not.toHaveBeenCalled()`（不是只断言自己被调了——那样三个都绑同一个 handler 也会绿） |
| 动作区点击**不冒泡** | `动作区点击不冒泡到卡片`：三个按钮**各验一次**；外加 `动作区空白处点击同样不冒泡` |
| **阴性对照** | `动作区之外的点击照常冒泡到卡片` —— 否则「不冒泡」可能是因为整张卡根本没绑 click |

## 4 产出
`web/components/hotspot-card-actions/HotspotCardActions.tsx`、`HotspotCardActions.test.tsx`（6 条）。
