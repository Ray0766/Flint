// HOTSPOT-07：合成结论句黑名单（前端复检用）。
//
// **唯一真相是后端** `flint/region/by_source_region.py#SYNTHESIS_BLACKLIST`（REGION-08）。
// 这里是它的前端副本，逐条同源——`SourceColumns.test.tsx` 有一条测试直接去读那份
// Python 源、把两边逐项比对：任一侧改了而另一侧没跟上，测试立刻红。
//
// 为什么前端也要有一份、而不是只在后端拦：合成句最容易在**渲染层**被重新引入
// （有人顺手在列表上方加一句「综合来看…」），那句话根本不经过后端。
//
// 为什么模式写在 .json 而不是这个 .ts 里：它们是**检测模式**不是界面文案，
// 里面的中文必须逐字保留（key 化会让它们不再匹配任何东西）。i18n 扫描面是 .ts/.tsx，
// 把数据放进 .json 既避开了误判，也如实表达了「这是数据不是文案」。
//
// 为什么不干脆两边共读一份文件：那要改动 REGION-08 已验收的模块去读外部文件，
// 而 DEC-003 定的触碰边界是既有文件只做注册点增量。副本 + 漂移检测是更小的改动面。

import blacklist from "./synthesis-blacklist.json";

export const SYNTHESIS_BLACKLIST: readonly string[] = blacklist.patterns;
