// GRAPH-16（隔离带·F15）：页签（图谱 / 树）+ 常驻可折叠 AI 栏。
//
// **AI 栏是常驻的**：折叠起来也仍然在场（一条可展开的窄边），而不是消失。
// 消失的话，用户下次要找它得先想起「它在哪个模式下才有」——那正是模式切换
// 带来的负担，而这张卡的立场就是不要模式。
//
// **无 mode 键**：状态只有 `tab` 与 `aiPanelCollapsed` 两个正交键（见 store 的说明）。
// 「默认 / AI」只作为**预设组合的文案**出现，NEVER 成为状态。
//
// **本卡是隔离带卡**（工单 §11-①，owner_review）：被划掉时只移除 `web/views/workbench-tabs/`
// 一个目录，容器 GRAPH-01 与其它 F 组卡不引用本卡任何东西——零下游破坏。

import type { JSX, ReactNode } from "react";
import { useState } from "react";

import { t } from "../../lib/i18n/t";
import { WorkbenchShell } from "../workbench-shell/WorkbenchShell";
import {
  applyPreset,
  describePreset,
  INITIAL_STATE,
  type WorkbenchTab,
  type WorkbenchTabsState,
} from "./workbenchTabsStore";

export type WorkbenchTabsProps = {
  graphView: ReactNode;
  treeView: ReactNode;
  aiPanel: ReactNode;
};

const TABS: readonly WorkbenchTab[] = ["graph", "tree"];

export function WorkbenchTabs({
  graphView,
  treeView,
  aiPanel,
}: WorkbenchTabsProps): JSX.Element {
  const [state, setState] = useState<WorkbenchTabsState>(INITIAL_STATE);
  const preset = describePreset(state);

  return (
    <div data-testid="workbench-tabs" data-preset={preset ?? ""}>
      <nav role="tablist">
        {TABS.map((tab) => (
          <button
            key={tab}
            type="button"
            role="tab"
            data-testid={`workbench-tab-${tab}`}
            data-tab={tab}
            aria-selected={state.tab === tab}
            onClick={() => setState((prev) => ({ ...prev, tab }))}
          >
            {t(`workbench.tab.${tab}`)}
          </button>
        ))}
        <button
          type="button"
          data-testid="workbench-preset-ai"
          onClick={() => setState(applyPreset("ai"))}
        >
          {t("workbench.preset.ai")}
        </button>
      </nav>
      <WorkbenchShell
        aside={
          <section
            data-testid="workbench-ai-panel"
            data-collapsed={String(state.aiPanelCollapsed)}
          >
            <button
              type="button"
              data-testid="workbench-ai-toggle"
              aria-expanded={!state.aiPanelCollapsed}
              onClick={() =>
                setState((prev) => ({
                  ...prev,
                  aiPanelCollapsed: !prev.aiPanelCollapsed,
                }))
              }
            >
              {t("workbench.ai_panel.toggle")}
            </button>
            {state.aiPanelCollapsed ? null : (
              <div data-testid="workbench-ai-panel-body">{aiPanel}</div>
            )}
          </section>
        }
      >
        <div data-testid="workbench-tabpanel" data-tab={state.tab}>
          {state.tab === "graph" ? graphView : treeView}
        </div>
      </WorkbenchShell>
    </div>
  );
}
