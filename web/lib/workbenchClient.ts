// PERSIST-02-b：把一张工作台图取回来（`GET /workbenches/{id}`）。
//
// ## 治的病
//
// `web/app/workbenches/[id]/page.tsx` 里写死 `const graph = null`，
// 文件头自述「端点建好之后，这里只要把 graph 从 null 换成取回来的那张图」——
// 那句话写下时确实**没有任何一条端点能把一张图读出来**。
// `PERSIST-02` 建了 `GET /workbenches/{id}`，这里是它的前端一侧。
//
// ## `null` 与空图 NEVER 挤进同一个表示
//
// `GraphWorkbench` 的 props 逐字写着：`null` = 没查过（画「接口未提供」），
// `{nodes: []}` = 查过了、空图（画空图引导）。所以本模块的返回值是
// **三态**而不是「图或者 null」：
//
// | 结果 | 意思 | 屏上 |
// |---|---|---|
// | `ok` | 取到了（可能是一张空图） | 画布 / 空图引导 |
// | `not_found` | 服务端说这张图不在（404 **带 `code`**） | 「没有这张工作台」 |
// | `unavailable` | 取不到（路由没挂 / 5xx / 网络不通） | 「接口未提供」，NEVER 画空图 |
//
// `not_found` 与 `unavailable` 分开的判法与 `cardActions.ts` 同源：
// **看 404 里有没有 `code`**。框架那种没有 `code` 的 404 是「路由没挂」，
// 该去问后端；带 `code` 的是「这个 id 不对」，该去问用户。
//
// ## 身份头必须发
//
// 端点会拿它比归属（别人的图回 404）。`API_USER_ID` 没配就不发——
// **NEVER 编一个身份**（`derefClient` / `cardActions` 的同一条口径）。
//
// ## 字段名在这里换一次，且只换一次
//
// 服务端说 `node_id` / `source_id`，画布那边的类型说 `nodeId` / `nameNative`。
// 转换只发生在本文件：两边各留一半的话，改一次字段名要在两处同时改，
// 而漏掉的那一处不会报错，只会安静地渲染成 `undefined`。

import { API_BASE, API_USER_ID } from "./apiBase";
import type { WorkbenchDetail } from "./types";
import type { WorkbenchGraph, WorkbenchNode } from
  "../components/graph-workbench/GraphWorkbench";
import type { GraphEdgeView } from "../components/graph-generate-gate/GenerateGate";

/** 服务端那一侧的形状。**一处定义**在 `types.ts`——
 * 那里是尺子（`check_fe_be_parity`）真正会去读的地方，
 * 在这里再抄一份的话两份会各自漂移，而尺子只看得见其中一份。 */
export type WorkbenchResponse = WorkbenchDetail;

export type WorkbenchResult =
  | { state: "ok"; graph: WorkbenchGraph; seedClusterId: string }
  | { state: "not_found" }
  | { state: "unavailable"; status: number | null };

const KINDS = ["cluster", "evidence_card", "topic"] as const;

function toNode(raw: WorkbenchResponse["nodes"][number]): WorkbenchNode {
  // 认不出的 `source_kind` 落回 `cluster`：画布只认这三种，
  // 而**丢掉一个节点比画错一个图标更坏**——用户会以为自己入台的东西没了。
  const kind = (KINDS as readonly string[]).includes(raw.source_kind)
    ? (raw.source_kind as WorkbenchNode["sourceKind"])
    : "cluster";
  return {
    nodeId: raw.node_id,
    sourceKind: kind,
    // `label` 是服务端存的那个名字；空的时候退回 id，NEVER 渲染成空白节点。
    nameNative: raw.label || raw.source_id,
    primary: raw.primary,
  };
}

function toEdge(raw: WorkbenchResponse["edges"][number]): GraphEdgeView {
  return {
    edgeId: raw.edge_id,
    fromNodeId: raw.from_node_id,
    toNodeId: raw.to_node_id,
    hypothesis: raw.hypothesis,
  };
}

export function toGraph(body: WorkbenchResponse): WorkbenchGraph {
  const nodes = body.nodes.map(toNode);
  // primary **由服务端说了算**（I12-1 图内恒 ≤1）。这里只是找出它是谁；
  // 一个都没有就是 `null`，NEVER 由前端挑一个顶上。
  const primary = nodes.find((n) => n.primary);
  return {
    nodes,
    edges: body.edges.map(toEdge),
    primaryNodeId: primary ? primary.nodeId : null,
  };
}

export async function fetchWorkbench(
  graphId: string,
  opts: { baseUrl?: string; userId?: string; fetchImpl?: typeof fetch } = {},
): Promise<WorkbenchResult> {
  const f = opts.fetchImpl ?? fetch;
  const headers: Record<string, string> = { accept: "application/json" };
  const userId = opts.userId ?? API_USER_ID;
  if (userId) headers["x-user-id"] = userId;

  let res: Response;
  try {
    res = await f(
      `${opts.baseUrl ?? API_BASE}/workbenches/${encodeURIComponent(graphId)}`,
      { headers },
    );
  } catch {
    // 网络整个打不通。**NEVER 落成空图**：空图说的是「查过了、是空的」。
    return { state: "unavailable", status: null };
  }

  if (res.status === 404) {
    // 有 `code` = 服务端认得这条路、只是这张图不在；没有 = 路由压根没挂。
    let code: unknown = undefined;
    try {
      code = ((await res.json()) as { code?: unknown }).code;
    } catch {
      code = undefined;
    }
    return code ? { state: "not_found" } : { state: "unavailable", status: 404 };
  }
  if (!res.ok) return { state: "unavailable", status: res.status };

  const body = (await res.json()) as WorkbenchResponse;
  return { state: "ok", graph: toGraph(body), seedClusterId: body.seed_cluster_id };
}
