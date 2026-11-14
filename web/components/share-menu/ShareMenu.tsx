// HOTSPOT-09：分享菜单（一键入台 / 分享给朋友 / 只读外链）。
//
// **入台走的是工作台那条既有链路**（GRAPH-02 的 `POST /workbenches/{id}/nodes`）。
// 另开一条的坏处不是多写代码，而是幂等键会分叉：同一个热点从广场入台一次、
// 从工作台入台一次，画布上会出现两张一模一样的卡片，而用户以为那是两个热点。
//
// **friend 项是一条诚实的缝**：后端 `share_with_friend` 抛 NotImplementedError
// （contracts_v04，SCHEMA-11）。前端这一半要做到的是——点它**什么都不发**。
// 一个看起来能点、点了却悄悄失败的菜单项，比明说「即将上线」糟得多。
//
// **外链项只开入口，NEVER 当场铸链接**：点一下菜单就 POST /share-links 等于
// 悄悄铸出一条**公开可读**的链接；铸不铸由随后的确认动作决定。
//
// 节点 id 由后端给，前端 NEVER 自己编一个：编出来的 id 与库里那条对不上，
// 后续对这个节点的任何操作都会落空。

import type { JSX } from "react";
import { useState } from "react";

import { t } from "../../lib/i18n/t";

export type ShareMenuProps = {
  workbenchId: string;
  sourceKind: "cluster" | "favorite";
  sourceId: string;
  fetchImpl?: typeof fetch;
  /** 入台成功后把后端给的 node_id 交出去 */
  onAdded?: (nodeId: string) => void;
  /** 打开外链创建流程（本菜单不铸链接） */
  onOpenShareLink?: () => void;
};

export function ShareMenu({
  workbenchId,
  sourceKind,
  sourceId,
  fetchImpl,
  onAdded,
  onOpenShareLink,
}: ShareMenuProps): JSX.Element {
  const [failed, setFailed] = useState(false);

  const addToWorkbench = async (): Promise<void> => {
    const send = fetchImpl ?? fetch;
    try {
      const res = await send(`/workbenches/${workbenchId}/nodes`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ source_kind: sourceKind, source_id: sourceId }),
      });
      if (!res.ok) {
        setFailed(true);
        return;
      }
      const body = (await res.json()) as { node_id: string };
      setFailed(false);
      onAdded?.(body.node_id);
    } catch {
      setFailed(true);
    }
  };

  return (
    <ul role="menu" data-testid="share-menu">
      <li
        role="menuitem"
        data-testid="share-menu-add-to-workbench"
        onClick={() => void addToWorkbench()}
      >
        {t("share.menu.add_to_workbench")}
      </li>
      <li role="menuitem" data-testid="share-menu-friend" aria-disabled="true">
        {t("share.menu.friend")}
      </li>
      <li
        role="menuitem"
        data-testid="share-menu-share-link"
        onClick={() => onOpenShareLink?.()}
      >
        {t("share.menu.share_link")}
      </li>
      {failed ? (
        <li data-testid="share-menu-error">{t("share.menu.add_failed")}</li>
      ) : null}
    </ul>
  );
}
