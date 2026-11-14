// K6-01：多工作台切换入口（切换 / 归档 / 恢复）。
//
// ## 形态照 Slack 的工作区切换器
//
// 一个常驻入口 → 展开成一份列表 → 点一项就切过去。**不做多层菜单**：
// 多台在本产品里是「同一个人的几个思考现场」，不是租户树。
// 出处与取舍写在 docs/trace/K6-01.md §3。
//
// ## 切的是台，不是模式（GRAPH-16）
//
// 状态只有两个正交的键：`currentId`（在哪台）与 `showArchived`（归档区展开与否）。
// 放一个 mode 键进来，它与这两个键就成了两份真相——`workbenchTabsStore.ts`
// 已经为同一件事付过一次代价，这里不再付第二次。
//
// ## 归档不是删除
//
// 归档的台仍然存在、仍可翻回（`flint/graph/multi.py` 的原话）。所以：
// 归档区里 **NEVER 有删除入口**——数据删除是 owner 人审节点，v0.4 内没有这条路径。
// 另外**最后一台不给归档**：归档掉全部会让用户落到一个没有工作台的界面，
// 而那个界面在本产品里根本不存在。

import type { JSX } from "react";
import { useState } from "react";

import { t } from "../../lib/i18n/t";

export type Workbench = {
  graphId: string;
  title: string;
  archived: boolean;
};

// 状态键恒为这两个：有测试逐字盯着它（GRAPH-16 同款守护）。
// 写成行注释而非 JSDoc：扫描器对跨行块注释有已知假阳性（DEC-013 / 卡 I18N-09），
// 而本文件的「零 CJK 字面量」判据正是靠剥行注释实现的。
export type WorkbenchSwitchState = {
  currentId: string;
  showArchived: boolean;
};

export const INITIAL_SWITCH_STATE: WorkbenchSwitchState = {
  currentId: "",
  showArchived: false,
};

// 可切换的台：**默认不含归档**（与 `list_workbenches` 的默认行为一致）。
export function visibleWorkbenches(all: Workbench[]): Workbench[] {
  return all.filter((w) => !w.archived);
}

// 归档区的台。与上面互补，两组永不重叠。
export function archivedOf(all: Workbench[]): Workbench[] {
  return all.filter((w) => w.archived);
}

export type WorkbenchSwitchProps = {
  workbenches: Workbench[];
  currentId: string;
  onSwitch: (graphId: string) => void;
  onArchive: (graphId: string) => void;
  onUnarchive: (graphId: string) => void;
};

export function WorkbenchSwitch({
  workbenches,
  currentId,
  onSwitch,
  onArchive,
  onUnarchive,
}: WorkbenchSwitchProps): JSX.Element {
  const [open, setOpen] = useState(false);
  const [showArchived, setShowArchived] = useState(INITIAL_SWITCH_STATE.showArchived);

  const live = visibleWorkbenches(workbenches);
  const archived = archivedOf(workbenches);
  const current = live.find((w) => w.graphId === currentId);
  const lastOne = live.length <= 1;

  return (
    <div className="workbench-switch" data-testid="workbench-switch">
      <button
        type="button"
        className="workbench-switch__trigger"
        data-testid="workbench-switch-trigger"
        aria-expanded={open}
        aria-label={t("workbench.switch.label")}
        onClick={() => setOpen((v) => !v)}
      >
        {current ? current.title : t("workbench.switch.empty")}
      </button>

      {open ? (
        <ul className="workbench-switch__list" data-testid="workbench-switch-list">
          {live.map((w) => (
            <li key={w.graphId} className="workbench-switch__row">
              <button
                type="button"
                className="workbench-switch__item"
                data-testid={`workbench-item-${w.graphId}`}
                data-graph-id={w.graphId}
                aria-current={w.graphId === currentId ? "true" : undefined}
                onClick={() => {
                  // 切到当前这台不重复触发：那是一次无意义的重载。
                  if (w.graphId !== currentId) onSwitch(w.graphId);
                }}
              >
                {w.title}
              </button>
              <button
                type="button"
                className="workbench-switch__archive"
                data-testid={`workbench-archive-${w.graphId}`}
                disabled={lastOne}
                title={lastOne ? t("workbench.switch.lastOne") : undefined}
                onClick={() => onArchive(w.graphId)}
              >
                {t("workbench.switch.archive")}
              </button>
            </li>
          ))}

          <li className="workbench-switch__row">
            <button
              type="button"
              className="workbench-switch__show-archived"
              data-testid="workbench-show-archived"
              aria-expanded={showArchived}
              onClick={() => setShowArchived((v) => !v)}
            >
              {t("workbench.switch.showArchived")}
            </button>
          </li>

          {showArchived ? (
            <li className="workbench-switch__row" data-testid="workbench-archived-section">
              <span className="workbench-switch__section">
                {t("workbench.switch.archivedSection")}
              </span>
              <ul className="workbench-switch__archived">
                {archived.map((w) => (
                  <li key={w.graphId} className="workbench-switch__row">
                    <span data-testid={`workbench-archived-${w.graphId}`}>{w.title}</span>
                    <button
                      type="button"
                      className="workbench-switch__unarchive"
                      data-testid={`workbench-unarchive-${w.graphId}`}
                      onClick={() => onUnarchive(w.graphId)}
                    >
                      {t("workbench.switch.unarchive")}
                    </button>
                  </li>
                ))}
              </ul>
            </li>
          ) : null}
        </ul>
      ) : null}
    </div>
  );
}
