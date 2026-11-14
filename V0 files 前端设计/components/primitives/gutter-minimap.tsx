// 出处槽缩略带 = 出处槽的缩影：与 EvidenceGutter 共用同一套派生真相 deriveGutterMarks，
// 绝不各算各的。缩略带每段取一枚"代表印记"（按优先级），编码「文档位置 + 类别」，
// NEVER 编码程度：每段固定等高、类别用图形/字形区分，无强度渐变/热力图/明度差。
"use client"

import type { Block } from "@/lib/types"
import { deriveGutterMarks, type GutterMarkKind } from "@/components/honesty/evidence-gutter"

// 缩略带每段只显示一枚字形。优先级：阻断 > 缺口 > 争议 > 保护 > 待复核 > 推测 > 无。
type MinimapCategory = "blocking" | "gap" | "disputed" | "locked" | "advisory" | "speculative" | "clean"

// 从共用派生结果收敛为单枚代表类别（不重算规则，只在派生结果上取优先级）。
function representativeCategory(block: Block): MinimapCategory {
  const marks = deriveGutterMarks(block)
  if (marks.some((m) => m.kind === "review" && m.severity === "blocking")) return "blocking"
  if (marks.some((m) => m.kind === "gap")) return "gap"
  if (marks.some((m) => m.kind === "disputed")) return "disputed"
  if (marks.some((m) => m.kind === "locked")) return "locked"
  if (marks.some((m) => m.kind === "review")) return "advisory"
  if (marks.some((m) => m.kind === "speculative")) return "speculative"
  return "clean"
}

const MARK: Record<MinimapCategory, { glyph: string; label: string; className: string }> = {
  blocking: { glyph: "▰", label: "阻断", className: "text-spark" },
  gap: { glyph: "⊗", label: "缺口", className: "text-ink-2" },
  disputed: { glyph: "◈", label: "争议", className: "text-ink" },
  locked: { glyph: "⊟", label: "保护", className: "text-ink-2" },
  advisory: { glyph: "◹", label: "待复核", className: "text-ink-2" },
  speculative: { glyph: "◌", label: "推测", className: "text-ink-3" },
  clean: { glyph: "·", label: "无附加状态", className: "text-ink-3" },
}

export function GutterMinimap({ blocks }: { blocks: Block[] }) {
  return (
    <nav aria-label="出处槽缩略带" className="flex flex-col gap-1.5">
      <p className="mb-1 font-mono text-[10px] leading-none text-ink-3">出处槽</p>
      {blocks.map((b) => {
        const cat = representativeCategory(b)
        const m = MARK[cat]
        return (
          <a
            key={b.block_id}
            href={`#${b.block_id}`}
            title={`${b.block_id} · ${m.label}`}
            className="group flex items-center gap-2 rounded-[4px] border border-transparent px-1 py-1 hover:border-rule focus:outline-none focus-visible:ring-1 focus-visible:ring-ink-3"
          >
            {/* 固定等高的位置条：所有段一样高，位置=文档顺序，绝无强度渐变 */}
            <span aria-hidden className="h-4 w-0.5 shrink-0 rounded-full bg-rail" />
            <span aria-hidden className={`font-mono text-[12px] leading-none ${m.className}`}>
              {m.glyph}
            </span>
            <span className="font-mono text-[10px] leading-none text-ink-3 opacity-0 transition-opacity group-hover:opacity-100">
              {m.label}
            </span>
          </a>
        )
      })}
    </nav>
  )
}
