// PLAZA-01：簇 → 卡面属性。**只做搬运，NEVER 做计算，也 NEVER 补一个没有的槽。**
//
// ## 广场这条端点能填几槽
//
// `GET /plaza/hot` 回的是 `PlazaCluster`：`cluster_id` / `canonical_name` /
// `category_id` / `status` / `first_seen` / `by_source` / `total_heat`。
// 对照卡面六槽——**地区、陈旧、Gate 判定这三槽它没有**。
//
// `first_seen` 是 `SLOT-01` 补上的：库里一直有这一列、端点先前查了不回。
// 剩下三槽各卡各的（`REGION-08` 要迁移 · `SLOT-02` 接 Revalidator · Gate 判定见 `DEC-012`）。
//
// 所以这三槽在广场上**逐槽隐藏**（卡面本来就这么写的）。
// NEVER 拿手边的字段去顶：`category_id` 不是地区、`status`（簇的活跃度）不是 Gate 判定。
// 顶上去的那一版看起来更「完整」，而它说的每一句都是假的。
//
// ## `category_id` 为什么不上产品面
//
// 它是内部 id（实测值 `cat-ai`）。`FB-10` 的分界原话：**A 类脚手架 = 开发要看的东西
// 跑到了产品面**，端点路径、内部 id、`X-User-Id` 三样点名在内。
// 改前那个 `ul/li` 版把 `cat-ai` 直接印在屏上，这次一并停掉；
// 它仍留在 `data-cluster-category` 上供取证用（取证认原值，人看产品语言）。
// 换成人读的类目名要走 `GET /categories`，那是另一张卡的事。

import type { HotspotCardProps } from "../hotspot-card/HotspotCard";
import type { PlazaCluster } from "../../lib/viewsClient";

export type PlazaCardProps = HotspotCardProps & {
  clusterId: string;
  categoryId: string;
  /** 后端给的热度，**原样搬运**——本屏不排序、不筛选、不合成任何数值。 */
  heat: number;
};

export function clusterToCard(cluster: PlazaCluster): PlazaCardProps {
  return {
    clusterId: cluster.cluster_id,
    categoryId: cluster.category_id,
    // 主行恒 name_native（B7）。广场这条端点给的权威名就是 `canonical_name`——
    // 它**不是**机翻派生物，所以进主行；没有译名槽可填，次要行因此不渲染（A7 降级）。
    nameNative: cluster.canonical_name,
    // SLOT-01：首见日期**原样搬运**，NEVER 在这里格式化、NEVER 算「几天前」。
    // 「3 天前」是相对**本机时钟**的——同一张卡在两台机器上会说不同的话，
    // 而截图取证里看不出哪一台是对的。要换人读写法，那是全局日期呈现的事，
    // 一处定义、他处引用（`t()` 那一层），不是在搬运层各写一份。
    // 没有这个字段（老数据 / 弱信号轨）就传 `null`：卡面**逐槽隐藏**，NEVER 顶一个「—」。
    firstSeen: cluster.first_seen ?? null,
    heat: cluster.total_heat,
  };
}
