// GRAPH-06：节点角色菜单（F5/F6）。
//
// **不弹确认框**：用户点第二个节点设主，意思已经很明确；再问一句「确定要替换吗」
// 是把系统的洁癖变成用户的负担。但降级**必须如实告诉他**——悄悄换掉主而不吭声，
// 他下次看这张图时会以为自己记错了。所以旧主降级出 toast、并点名是谁被降。
//
// **谁被降是服务端算的**（flint/graph/roles.py 在临界区内定，I12-1）。本组件只呈现
// 回值，NEVER 自己推断：本地推断在并发下必然与服务端不一致，而用户看到的是本地那份。
// `currentPrimaryId` 只用于把当前态标出来，NEVER 参与降级判断。
//
// 失败不谎报成功：设主没成就出错误态且不出 toast——一条「已替换主节点」的提示
// 配上一个没变的图，比什么都不说更让人困惑。

import type { JSX } from "react";
import { useState } from "react";

import { t } from "../../lib/i18n/t";

export type NodeRole = "primary" | "secondary" | "auxiliary";

/** 服务端回值：非空 = 有一个旧主被降级。 */
export type RoleChangeResult = { demotedNodeId: string | null };

export type GraphRolesProps = {
  nodeId: string;
  /** 当前主（仅用于标出当前态） */
  currentPrimaryId?: string | null;
  onSetRole: (nodeId: string, role: NodeRole) => Promise<RoleChangeResult>;
};

const ROLES: readonly NodeRole[] = ["primary", "secondary", "auxiliary"];

export function GraphRoles({
  nodeId,
  currentPrimaryId,
  onSetRole,
}: GraphRolesProps): JSX.Element {
  const [demoted, setDemoted] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  const choose = async (role: NodeRole): Promise<void> => {
    try {
      const result = await onSetRole(nodeId, role);
      setFailed(false);
      setDemoted(result.demotedNodeId);
    } catch {
      setFailed(true);
      setDemoted(null);
    }
  };

  return (
    <div data-testid="graph-roles" data-current-primary-id={currentPrimaryId ?? ""}>
      <ul role="menu">
        {ROLES.map((role) => (
          <li
            key={role}
            role="menuitem"
            data-role={role}
            data-testid={`graph-role-${role}`}
            onClick={() => void choose(role)}
          >
            {t(`graph.role.${role}`)}
          </li>
        ))}
      </ul>
      {demoted !== null ? (
        <div
          data-testid="graph-role-toast"
          data-demoted-node-id={demoted}
          role="status"
        >
          {t("graph.role.demoted", { node: demoted })}
        </div>
      ) : null}
      {failed ? (
        <div data-testid="graph-role-error">{t("graph.role.failed")}</div>
      ) : null}
    </div>
  );
}
