// why_now 呈现件（P4 主题列表 / P5 主题详情共用）
//
// **技术约束清单第 13 条**：`why_now.speculative == true` MUST 降权，且**抑制溯源入口**，
// NEVER 升格为已证。这里的「抑制溯源入口」落到实处是两件事：
//   1. 推测态下 evidences 的 `citation_id` **不渲染成可取证的引用位**——
//      因为它是模型的联想链条，不是经对齐的证据；把它画成引用会让读者以为可溯源。
//   2. 明写这条判断「未经证据对齐」，读者据此自行判断。
// 非推测态才把 citation_id 作为引用位呈现（解引用端点未建 → 只显 id，见清单第 3 条）。
//
// 非颜色载体：推测态用**虚线边 + 降透明度 + CircleDashed 记号**；已证态用实线边 + Link2 记号。
// 灰度下靠边缘质地与记号形状即可分辨，NEVER 只靠颜色。
import { CircleDashed, Link2 } from "lucide-react";
import type { TopicWhyNow } from "@/lib/types";

export function WhyNowPanel({ why, compact = false }: { why: TopicWhyNow; compact?: boolean }) {
  const spec = why.speculative;
  return (
    <div
      className={
        spec
          ? "border border-dashed border-rail bg-raised/60 p-4"
          : "border border-rule bg-surface p-4"
      }
      style={{ borderRadius: "var(--radius-card)" }}
    >
      <div className="flex items-center gap-2">
        {spec ? (
          <CircleDashed className="h-3.5 w-3.5 text-ink-3" strokeWidth={1.5} aria-hidden />
        ) : (
          <Link2 className="h-3.5 w-3.5 text-ink-2" strokeWidth={1.5} aria-hidden />
        )}
        <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-ink-3">
          why_now · speculative {String(spec)}
        </span>
      </div>

      {/* 降权：推测态正文用次级墨色，不与已证结论同重 */}
      <p className={`mt-3 text-[14px] leading-[1.75] ${spec ? "text-ink-3" : "text-ink-2"}`}>
        {why.claim}
      </p>

      {spec ? (
        // 抑制溯源入口：不把 citation_id 画成引用位，并说清为什么
        <div className="mt-4 border-t border-rule pt-3">
          <p className="text-[12px] leading-[1.7] text-ink-3">
            这是<span className="text-ink-2">推测</span>——未经证据对齐，因此此处
            <span className="text-ink-2">不提供溯源入口</span>。
            后端仍附了 {why.evidences.length} 条联想线索，但它们是模型的推理链条、不是已证引用，
            界面不把它们呈现为可取证的出处。
          </p>
          {!compact && why.evidences.length > 0 ? (
            <ul className="mt-3 space-y-1.5">
              {why.evidences.map((e, i) => (
                <li key={i} className="text-[12px] leading-[1.6] text-ink-3">
                  · {e.event}
                  {e.event_date !== null ? (
                    <span className="ml-2 font-mono text-[10px]">{e.event_date}</span>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : why.evidences.length === 0 ? (
        <p className="mt-4 border-t border-rule pt-3 font-mono text-[11px] text-ink-3">
          evidences 为空数组（后端未附线索）。
        </p>
      ) : (
        // 非推测：citation_id 作为引用位呈现；解引用端点未建 → 只显 id（清单第 3 条）
        <div className="mt-4 border-t border-rule pt-3">
          <p className="mb-2 font-mono text-[10px] uppercase tracking-[0.12em] text-ink-3">
            evidences · {why.evidences.length}
          </p>
          <ul className="space-y-2">
            {why.evidences.map((e, i) => (
              <li key={i} className="text-[12px] leading-[1.65] text-ink-2">
                {e.event}
                <span className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-0.5">
                  {e.event_date !== null ? (
                    <span className="tabular font-mono text-[10px] text-ink-3">
                      event_date · {e.event_date}
                    </span>
                  ) : null}
                  {e.citation_id !== null ? (
                    <span className="break-all font-mono text-[10px] text-ink-3">
                      citation_id · {e.citation_id}
                      <span className="ml-1.5">（解引用端点未提供，此处只显引用位）</span>
                    </span>
                  ) : (
                    <span className="font-mono text-[10px] text-ink-3">citation_id · null</span>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
