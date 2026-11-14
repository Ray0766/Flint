// 状态：PlazaCluster.by_source 的四个源键 → 固定 2px 方形源印（仅类别识别，恒定尺寸，不表强弱）
import type { SourceKey } from "@/lib/types"

// by_source 键 → globals.css 源色 token 的显式映射。
// 四源色仅承载「哪一源」这一纯类别信息；面积恒定 8px 方形，绝不用大小/明度编码分值高低。
const SRC_MAP: Record<SourceKey, { varName: string; label: string }> = {
  arxiv: { varName: "--src-arxiv", label: "arxiv" },
  ghtrend: { varName: "--src-github", label: "ghtrend" },
  gtrends: { varName: "--src-trends", label: "gtrends" },
  weibo: { varName: "--src-weibo", label: "weibo" },
}

export function SourceMark({ source }: { source: SourceKey }) {
  const meta = SRC_MAP[source]
  return (
    <span
      className="inline-block h-2 w-2 shrink-0 rounded-[1px] align-middle"
      style={{ backgroundColor: `var(${meta.varName})` }}
      aria-hidden
    />
  )
}

// 源印 + 源名 + 分值（等宽）。分值只作数字如实呈现，不做条形/百分比等程度可视化。
export function SourceScore({ source, score }: { source: SourceKey; score: number }) {
  const meta = SRC_MAP[source]
  return (
    <span className="inline-flex items-center gap-1.5">
      <SourceMark source={source} />
      <span className="font-mono text-[12px] text-ink-2">{meta.label}</span>
      <span className="tabular font-mono text-[12px] text-foreground">{score}</span>
    </span>
  )
}
