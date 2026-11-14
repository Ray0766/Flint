// GRAPH-16（隔离带·F15）：工作台页签 + 常驻可折叠 AI 栏的**状态**。
//
// ## 状态树里没有 mode
//
// 「默认模式 / AI 模式」是用户心智，不是系统状态。真放一个 `mode` 键进来，
// 它与「当前页签」「AI 栏是否折叠」就成了**两份真相**：用户点开 AI 栏时 mode 该不该变？
// 切到树页签时 mode 又是什么？每加一个入口就要回答一次，而任何一次答得不一致，
// 界面上就会出现「模式说是 A、页签显示 B」。
//
// 所以状态只有**两个正交的键**：`tab`（图谱 / 树）与 `aiPanelCollapsed`（折叠与否）。
// 「默认 / AI」保留在**预设组合**这一层：预设只是一次性把这两个键设成某个组合的快捷方式，
// 设完就没它的事了——它 NEVER 作为状态被存起来。
//
// 这条对应 §11-① 的工单立场：若 owner 坚持要 mode，替代是**派生只读** mode
// （由 tab × 折叠态 算出、不落盘、不可直写）；本模块已把派生函数留好（`describePreset`），
// 那条替代路径只需在 UI 层展示它，改动仍只落本卡。

export type WorkbenchTab = "graph" | "tree";

/** 状态键集恒为这两个：有测试逐字盯着它。 */
export type WorkbenchTabsState = {
  tab: WorkbenchTab;
  aiPanelCollapsed: boolean;
};

export const INITIAL_STATE: WorkbenchTabsState = {
  tab: "graph",
  aiPanelCollapsed: true,      // 默认组合：图谱页签 + AI 栏折叠
};

/** 预设：一次性把两个键设成某个组合。**不落状态**，设完即弃。 */
export const PRESETS: Record<string, WorkbenchTabsState> = {
  default: { tab: "graph", aiPanelCollapsed: true },
  ai: { tab: "graph", aiPanelCollapsed: false },
};

export function applyPreset(name: keyof typeof PRESETS): WorkbenchTabsState {
  return { ...PRESETS[name] };
}

// 由当前两个键**派生**出预设名（只读，供文案层展示）。
//
// 派生而不是存储：存起来就又有了第二份真相。派生值算不出来时返回 null——
// NEVER 硬塞一个「default」，那会让一个并不匹配任何预设的组合看起来像是默认态。
//
// （写成行注释而非 JSDoc，是因为扫描器对跨行块注释有已知假阳性——
//   根因与修法都记在 DEC-013 / 卡 I18N-09；在它修好之前不给自己留一个假红。）
export function describePreset(state: WorkbenchTabsState): string | null {
  for (const [name, preset] of Object.entries(PRESETS)) {
    if (preset.tab === state.tab && preset.aiPanelCollapsed === state.aiPanelCollapsed) {
      return name;
    }
  }
  return null;
}
