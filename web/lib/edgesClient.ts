// EDGES-UI：画布连线落盘（`POST /workbenches/{graph_id}/edges`）。
//
// ## 连线**必须带假设**
//
// 一条没有假设的边说不出两端为什么被连起来（冻结件 `GraphEdge.__post_init__`
// 逐字拒空）。空假设走**既有的那一个** code：`422 EMPTY_HYPOTHESIS`——
// `docs/blocked/EMPTY-HYPOTHESIS-TWO-CODES.md` 已经定过一次，
// **NEVER 再分叉出第二个**（分叉之后调用方要按两套规矩判同一件事）。
//
// ## 存不下就 NEVER 把线留在画布上
//
// 与 `LocaleSettings` 那条「NEVER 回滚成旧值假装成功」是同一条纪律的两个方向：
// 那边禁的是「失败了把屏改回去」，这边禁的是「失败了把屏留在新样子」。
// 两者的共同点是**屏上显示的东西没有依据**。

import { API_BASE, API_USER_ID } from "./apiBase";

// **MUST 是 `export interface`**：`check_fe_be_parity` 只认这一种写法。
// 写成 `type` 时它匹到了另一个**四字段**的接口，于是报「少了 graph_id」——
// 而这份类型明明五个字段都在。**本批第三次撞同一条**
// （`PERSIST-02` · `FAV-WRITES` 各一次），所以这句注释写在这里而不是 trace 里。
export interface EdgeSaved {
  edge_id: string;
  graph_id: string;
  from_node_id: string;
  to_node_id: string;
  hypothesis: string;
}

export type EdgeResult =
  | { state: "ok"; edge: EdgeSaved }
  /** 假设是空的。**这一条有自己的名字**，NEVER 与下面那条合并。 */
  | { state: "empty_hypothesis"; message: string }
  /** 两端有一头不在这张图里（悬空边），或别的校验不过。 */
  | { state: "rejected"; message: string }
  | { state: "failed"; status: number | null };

export async function createEdge(
  graphId: string,
  edge: { edgeId: string; fromNodeId: string; toNodeId: string; hypothesis: string },
  opts: { baseUrl?: string; fetchImpl?: typeof fetch } = {},
): Promise<EdgeResult> {
  const f = opts.fetchImpl ?? fetch;
  const headers: Record<string, string> = { "content-type": "application/json" };
  // 没配身份就不发这个头——**NEVER 编一个身份**（全仓同一条口径）。
  if (API_USER_ID) headers["x-user-id"] = API_USER_ID;
  const url = `${opts.baseUrl ?? API_BASE}/workbenches/${encodeURIComponent(graphId)}/edges`;

  let res: Response;
  try {
    res = await f(url, {
      method: "POST",
      headers,
      body: JSON.stringify({
        edge_id: edge.edgeId,
        from_node_id: edge.fromNodeId,
        to_node_id: edge.toNodeId,
        hypothesis: edge.hypothesis,
      }),
    });
  } catch {
    return { state: "failed", status: null };
  }

  if (res.status === 422) {
    const body = (await res.json()) as { code?: string; message?: string };
    // 空假设与悬空边**各说各的**：前者用户去补一句话，后者用户去看两端选对没有。
    return body.code === "EMPTY_HYPOTHESIS"
      ? { state: "empty_hypothesis", message: body.message ?? "" }
      : { state: "rejected", message: body.message ?? "" };
  }
  if (!res.ok) return { state: "failed", status: res.status };
  return { state: "ok", edge: (await res.json()) as EdgeSaved };
}
