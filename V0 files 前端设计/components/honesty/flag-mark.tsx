// 证据卡旗标 flags（P2 工作台）· EvidenceCard.flags
//
// **三种各自可辨，NEVER 合并成一个统一标签**（技术约束清单第 10 条）。
// 每种同时具备三重区分，灰度下也分得开（第 4 条）：
//   novelty  · 新奇 → 星芒记号 + 实线边
//   momentum · 动量 → 箭头记号 + 双线底边
//   revival  · 复燃 → 回环记号 + 虚线边
// 颜色一律墨色（不用告警色、不用硫磺）——形状与边缘质地才是载体。
import { Sparkle, MoveUpRight, RotateCcw, Tag } from "lucide-react";

const KNOWN: Record<
  string,
  { label: string; Icon: typeof Sparkle; edge: string }
> = {
  novelty: { label: "novelty · 新奇", Icon: Sparkle, edge: "border-solid border-ink-3" },
  momentum: { label: "momentum · 动量", Icon: MoveUpRight, edge: "border-solid border-b-2 border-ink-2" },
  revival: { label: "revival · 复燃", Icon: RotateCcw, edge: "border-dashed border-rail" },
};

export function FlagMark({ flag }: { flag: string }) {
  const known = KNOWN[flag];
  // 后端出现契约外的新旗标时：如实原样显示，NEVER 吞掉、NEVER 归并到已知的三种里。
  const { label, Icon, edge } = known ?? {
    label: flag,
    Icon: Tag,
    edge: "border-dotted border-ink-3",
  };
  return (
    <span
      className={`inline-flex items-center gap-1.5 border px-2 py-1 font-mono text-[11px] text-ink-2 ${edge}`}
      style={{ borderRadius: "var(--radius)" }}
      title={known === undefined ? `契约外旗标：${flag}（原样呈现）` : label}
    >
      <Icon className="h-3.5 w-3.5" strokeWidth={1.5} aria-hidden />
      {label}
    </span>
  );
}
