// 干预门控的**唯一真相**（清单第 20 条）。
//
// 规则：受保护块（locked ∨ author==="user" ∨ user_modified）**不提供任何干预控件**——
// 是「不存在」，不是「置灰」。任何屏都 MUST 经这一个函数取可用动作，
// NEVER 各屏自己再判一遍（判重就会漂移，漂移就会漏）。
import { isProtected, type Block } from "@/lib/types";

export type BlockIntervention = "lock" | "regenerate" | "dispute";

/** 受保护 → 空数组（调用方据此**不渲染**控件区，而不是渲染后 disabled）。 */
export function availableBlockInterventions(block: Block): BlockIntervention[] {
  if (isProtected(block)) return [];
  return ["lock", "regenerate", "dispute"];
}

/** 受保护的具体原因（只用于如实标注，不参与门控判断）。 */
export function protectionReason(block: Block): string | null {
  if (block.locked) return "locked";
  if (block.author === "user") return 'author="user"';
  if (block.user_modified) return "user_modified";
  return null;
}
