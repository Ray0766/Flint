// DS-02：Gate 四分类 → `_ds` 状态记号。
//
// ## 为什么这张表只有两档，而不是四档
//
// 素材里的卡片顶行右上角是四个**互不相同**的记号，很想让 Gate 的四分类一一对上。
// 核过之后不能那么做：`_ds` 的八态在本仓**每一个都已经有固定含义**——
//
// | `_ds` 记号 | 本仓已经用它说什么 |
// |---|---|
// | `disputed` | fact 的 `status=="disputed"`（S2-4：NEVER 被新生成引用） |
// | `sealed` | block 被锁（S2-5 受保护 block） |
// | `degraded` | B7 / E6 的降级生成 |
// | `speculative` | claim 还没提升成 fact |
// | `review` | 待复核 |
// | `blocking` | 阻塞 / 409 / 503 |
//
// 把 `B_red_ocean` 涂成 `disputed`，屏上「这条结论有争议」与「这个赛道是红海」
// 就会共用一个记号——而前者是铁律级的事实状态，后者是一个判定结论。
// **借一个已经有主的记号去说另一件事，比不给记号更坏。**
//
// 所以这里只做零冲突的那一档：
//
// - `D_insufficient` → `void`：语义逐字相同（证据不足 = 有形空缺）；
// - 其余三类 → `verified`：它们的共同点是「判定已出且全引用」（Gate① 铁律），
//   **分类本身由标签文字承载**（人类标签在 `DS-03`）。
//
// 这一档在 `DECISIONS-v04.md` 登记为 DEC-034，并在第 5 批完成态报告里点名请 owner 复核：
// 若 owner 要四档各有各的记号，那是**给 `_ds` 加记号**，不是借现成的。

import type { DsStatus } from "../shell/DsStatusMark";

/** `contracts/models.py:638` 的 `Verdict` 判别联合，逐字。 */
export type Verdict =
  | "A_infeasible"
  | "B_red_ocean"
  | "C_opportunity"
  | "D_insufficient";

export function verdictStatus(verdict: string): DsStatus {
  return verdict === "D_insufficient" ? "void" : "verified";
}
