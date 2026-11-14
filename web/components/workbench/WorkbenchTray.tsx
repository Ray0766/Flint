import type { JSX } from "react";

import { t } from "../../lib/i18n/t";

/**
 * `WB-02`：中栏那条「本次组合」。
 *
 * 蓝本第 126~135 行：输入框上方一条虚线框，里面是已选卡片的 chip，
 * 每个 chip 带一个 `×`。形状照做。
 *
 * ## 它显示的**必须是数据源里的那几条**
 *
 * 第 13 批那条补充：正向判据要覆盖的不只是「长什么样」，
 * 还有「显示的是不是对的东西」。所以这条组合里每个 chip 都带
 * `data-wb-tray-id`（那一条的簇 id）与人读的名字，两样都由上面传下来，
 * **本组件一个字都不加工**——加工过的话，屏上那个名字与它代表的那条
 * 就可能不是同一件事，而这在屏上完全看不出来。
 *
 * ## 计数与清单是同一份东西的两种说法
 *
 * 计数恒在（哪怕一条没选）——只在选了之后才出现的话，
 * 用户不知道这里本来该有东西（`ENTRY-04` 那条计数条的既有理由，一字不变）。
 */

export type TrayItem = {
  clusterId: string;
  /** 人读的名字。**上游给什么就显示什么**，本组件不截断、不改写。 */
  name: string;
};

export type WorkbenchTrayProps = {
  items: TrayItem[];
  onRemove: (clusterId: string) => void;
};

export function WorkbenchTray({ items, onRemove }: WorkbenchTrayProps): JSX.Element {
  return (
    <div className="wb-tray" data-wb-tray="true" data-wb-tray-count={items.length}>
      <span className="wb-tray__title">{t("wb.tray.title")}</span>
      <span className="wb-tray__count" data-wb-tray-counter="true">
        {t("wb.tray.count", { n: items.length })}
      </span>
      {items.length === 0 ? (
        <span className="wb-tray__empty" data-wb-tray-empty="true">
          {t("wb.tray.empty")}
        </span>
      ) : (
        <ul className="wb-tray__list">
          {items.map((item) => (
            <li
              key={item.clusterId}
              className="wb-tray__chip"
              data-wb-tray-id={item.clusterId}
            >
              <span className="wb-tray__chip-label">{item.name}</span>
              <button
                type="button"
                className="wb-tray__chip-remove"
                data-wb-tray-remove={item.clusterId}
                aria-label={t("wb.tray.remove")}
                onClick={() => onRemove(item.clusterId)}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
