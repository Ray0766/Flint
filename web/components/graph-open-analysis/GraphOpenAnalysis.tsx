// GRAPH-05：双击节点开分析抽屉（F4，不离台）。
//
// **不离台**是这张卡的全部：用户正在画布上摆关系，点开一个热点看细节，
// 看完要能立刻回到刚才那张图。一旦跳路由，画布状态（选中、位置、未落盘的摆放）
// 就得靠恢复逻辑重建，而恢复得不完整的地方用户会当成「我刚才白摆了」。
// 所以这里既不 push 路由、也不开新窗口——抽屉就地展开，画布始终在场。
//
// **抽屉里装的是那个分析视图本体**（HOTSPOT-03 的 AnalysisView），不是它的复刻。
// 复刻的后果是同一个热点在画布上和分析页上显示出不同的东西，而用户以为
// 自己看的是同一份分析。
//
// 抽屉 `aria-modal="false"`：它不是模态。画布仍然可交互，这与「不离台」是一回事——
// 若把画布罩死，那与跳走一页的区别只剩视觉。
//
// 单击不开：画布上点一下是选中。点一下就弹出一屏东西，会让框选、拖动这些
// 以单击起手的操作变得处处踩雷。

import type { JSX, ReactNode } from "react";
import { useState } from "react";

import { t } from "../../lib/i18n/t";
import { AnalysisView } from "../../views/analysis/AnalysisView";

export type GraphOpenAnalysisProps = {
  clusterId: string;
  /** Gate① 判定所在的既有 job；由调用方给出（DEC-010/DEC-012） */
  verdictJobId?: string | null;
  fetchImpl?: typeof fetch;
  /** 画布上的节点本体 */
  children: ReactNode;
};

export function GraphOpenAnalysis({
  clusterId,
  verdictJobId,
  fetchImpl,
  children,
}: GraphOpenAnalysisProps): JSX.Element {
  const [open, setOpen] = useState(false);

  return (
    <div data-testid="graph-open-analysis">
      <div
        data-testid="graph-open-analysis-trigger"
        onDoubleClick={() => setOpen(true)}
      >
        {children}
      </div>
      {open ? (
        <aside
          data-testid="graph-analysis-drawer"
          role="dialog"
          aria-modal="false"
          aria-label={t("graph.analysis.drawer.title")}
        >
          <button
            type="button"
            data-testid="graph-analysis-drawer-close"
            onClick={() => setOpen(false)}
          >
            {t("graph.analysis.drawer.close")}
          </button>
          <AnalysisView
            clusterId={clusterId}
            verdictJobId={verdictJobId}
            fetchImpl={fetchImpl}
          />
        </aside>
      ) : null}
    </div>
  );
}
