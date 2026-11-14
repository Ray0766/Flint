// 预留位（清单 E 组第 32 条 · R1/R2/R3/R4 共用）
//
// 规则：端点未建的功能 MUST **明确写「端点未建」**，
// NEVER 做成看起来能用的假功能——不给可点控件、不显任何编造的数值。
// 形态：虚线边 + 中空记号（灰度下也一眼看出是「未建」而非「加载中」或「为空」）。
import { Construction } from "lucide-react";

export function UnbuiltEndpoint({
  title,
  endpoint,
  why,
  children,
}: {
  title: string;
  /** 未来的端点形状；写清楚将来接哪一支，而不是含糊带过 */
  endpoint: string;
  why: string;
  children?: React.ReactNode;
}) {
  return (
    <section
      className="border border-dashed border-rail bg-raised p-5"
      style={{ borderRadius: "var(--radius-card)" }}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Construction className="h-4 w-4 text-ink-3" strokeWidth={1.5} aria-hidden />
        <h3 className="text-[14px] font-medium text-ink">{title}</h3>
        <span
          className="border border-rail px-2 py-0.5 font-mono text-[10px] text-ink-2"
          style={{ borderRadius: "var(--radius)" }}
        >
          端点未建
        </span>
      </div>
      <p className="mt-3 break-all font-mono text-[11px] text-ink-3">{endpoint}</p>
      <p className="mt-2 max-w-[42em] text-[13px] leading-[1.7] text-ink-2">{why}</p>
      {children}
      <p className="mt-3 font-mono text-[10px] leading-[1.6] text-ink-3">
        此处不提供任何可点控件、不显示任何数值——没有端点就没有数据，界面不代为编造。
      </p>
    </section>
  );
}
