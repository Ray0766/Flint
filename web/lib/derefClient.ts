// FB-09：解引用客户端——把正文里的六类 id 换成内容。
//
// 六条通道对应 `flint/api/deref.py` 的六个端点（FB-04~08）。本模块只做两件事：
// 拼路径、判「拿到了还是没拿到」。
//
// ## 唯一的产品规则：拿不到就说拿不到
//
// 端点不可用（404 / 5xx / 网络整个打不通）时返回 `unavailable` **并把原 id 带回去**：
//
// - **NEVER 空白**——空白读起来是「这里本来就没东西」，而真相是「这里有东西但没取到」；
// - **NEVER 编造**——编出来的内容没有出处，而这套系统的第一条铁律是「结论必有引用」。
//
// 所以 `unavailable` 的结果里**没有** `data` 字段：没有内容就是没有内容，
// 调用方拿不到一个「看起来像内容」的东西去渲染。
//
// ## 全离线可测
//
// `fetchImpl` 注入（与 `topicClient` / `jobClient` 同一口径，S2-7 CI 恒不联网）。
//
// ## FIX-16：身份头**必须发**，而这里一直没发
//
// `flint/api/deref.py` 的六条端点都写着 `x_user_id: str = Header()`——**必填**。
// 不带这个头，端点回 422；带一个不是 owner 的身份，回 404（`404 而不是 403`：
// 403 等于告诉对方「这个 id 存在，只是不给你看」，状态码本身就泄露了存在性）。
//
// 而本模块此前只发 `Accept`。报告屏之所以还能看到事实与价格，
// **恰恰因为它打的是一个尚未重启、还不要求身份头的旧后端进程**——
// 那个进程一换，报告屏就会整片丢内容，而屏上只会说「取不到」。
//
// 身份从配置来（`API_USER_ID`），**没配就不发**：发一个编出来的身份
// 会让服务端把别人的数据当成你的（`FB-10` 的 A 类里 `X-User-Id` 逐字点名）。
// 这与 `cardActions.ts` 里写端点的那段是同一条口径。

import { API_USER_ID } from "./apiBase";

export type DerefKind = "fact" | "price" | "citation" | "chart" | "card" | "hints";

export type DerefResult =
  | { state: "resolved"; kind: DerefKind; id: string; data: unknown }
  | { state: "unavailable"; kind: DerefKind; id: string; status: number | null };

export interface DerefOptions {
  baseUrl: string;
  fetchImpl?: typeof fetch;
  /**
   * 调用方身份。缺省取 `API_USER_ID`（部署配置）。
   *
   * **空串 = 没配 = 不发这个头**，服务端会照实回 422，
   * 屏上于是显示「取不到」——而不是我们假装有一个用户。
   */
  userId?: string;
  // 价格通道要数量：金额由后端算，前端 NEVER 自己乘（FB-05 的判据）。
  quantity?: number;
}

// id 进 URL 一律转义：带斜杠的 id 不转义就变成了另一条路径，
// 而那条路径可能真的存在——那时候拿回来的是**别人的内容**。
const enc = encodeURIComponent;

export const DEREF_PATHS: Record<DerefKind, (id: string, quantity?: number) => string> = {
  fact: (id) => `/facts/${enc(id)}`,
  price: (id, quantity) => `/price-entries/${enc(id)}?quantity=${quantity ?? 1}`,
  citation: (id) => `/citations/${enc(id)}`,
  chart: (id) => `/charts/${enc(id)}`,
  card: (id) => `/cards/${enc(id)}`,
  hints: (id) => `/hints/${enc(id)}`,
};

export async function deref(
  kind: DerefKind,
  id: string,
  options: DerefOptions,
): Promise<DerefResult> {
  const doFetch = options.fetchImpl ?? fetch;
  const url = `${options.baseUrl}${DEREF_PATHS[kind](id, options.quantity)}`;
  const headers: Record<string, string> = { Accept: "application/json" };
  const userId = options.userId ?? API_USER_ID;
  if (userId) headers["x-user-id"] = userId;
  let response: Response;
  try {
    response = await doFetch(url, { headers });
  } catch {
    // 网络整个打不通也是「拿不到」的一种，NEVER 把异常抛给调用方自己判——
    // 每个调用点各判一次，迟早有一处判漏，而判漏的表现就是一片空白。
    return { state: "unavailable", kind, id, status: null };
  }
  if (!response.ok) {
    return { state: "unavailable", kind, id, status: response.status };
  }
  return { state: "resolved", kind, id, data: await response.json() };
}
