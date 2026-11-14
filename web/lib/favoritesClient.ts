// FAV-WRITES：收藏那三条写操作的客户端。
//
// ## 三条各说各的，NEVER 合成一句「操作失败」
//
// 卡面逐字：三条各自的失败态各说各的。理由不是措辞好看——
// 三条失败之后用户该做的事完全不同：
//
// | 操作 | 失败意味着 | 用户该做什么 |
// |---|---|---|
// | 取消收藏 | 那一条**还在**列表里 | 再点一次，或去查后端 |
// | 更新到最新 | 收藏还在，**快照没换** | 稍后再试；内容本身没丢 |
// | 看陈旧 | **不知道**它旧没旧 | 什么都不改——NEVER 显示成「最新」 |
//
// 合成一句的话，第三条会被读成前两条：用户以为自己刚才那一下没生效，
// 而其实是**我们没查到**。
//
// ## 身份头必须发
//
// 三条都按归属判（陌生人 NEVER 看到别人的收藏，`PERSIST-01` 定的不变量）。
// `API_USER_ID` 没配就不发——**NEVER 编一个身份**（全仓同一条口径）。

import { API_BASE, API_USER_ID } from "./apiBase";

export type FavWriteResult<T> =
  | { state: "ok"; data: T }
  | { state: "not_found" }
  | { state: "failed"; status: number | null };

/** `POST /favorites/{id}/staleness` 的响应。**字段名照后端实况**。
 *
 * 第一版我把陈旧那一格写成了 `stale`，而后端回的是 `snapshot_stale`——
 * 对账器当场报 `field_mismatch`，**而它是对的**：
 * 名字对不上时读出来的恒是 `undefined`，屏上会安静地显示「没判过」，
 * 而库里其实判过了。
 *
 * 两态各带各的解释字段：
 * - `checked`   → `snapshot_stale`（判过了，旧还是不旧）；
 * - `not_checked` → `missing` + `reason`（**没判过**，NEVER 读成「最新」）。
 */
// **MUST 是 `export interface`**：`tools/check_fe_be_parity.py#_frontend_interfaces`
// 只认这一种写法，写成 `type` 的话它报「前端根本没建这条端点的类型」，
// 而类型明明就在这儿（`PERSIST-02` 踩过一次，本卡第二次）。
export interface StalenessAnswer {
  favorite_id: string;
  status: "checked" | "not_checked";
  /** 只有 `checked` 时才有。缺席 = 没判过，NEVER 折成 `false`。 */
  snapshot_stale?: boolean;
  /** 只有 `not_checked` 时才有：缺的是什么、为什么。 */
  missing?: string[];
  reason?: string;
}

function headers(): Record<string, string> {
  const h: Record<string, string> = { accept: "application/json" };
  if (API_USER_ID) h["x-user-id"] = API_USER_ID;
  return h;
}

/** 把一次响应翻成三态。**只管读，不管发**——见下面每条自己的 `fetch`。 */
async function read<T>(
  res: Response, parse: (res: Response) => Promise<T>,
): Promise<FavWriteResult<T>> {
  // 404 单独一档：**这一条收藏不在**（或不是你的）——与「后端挂了」不是一回事。
  if (res.status === 404) return { state: "not_found" };
  if (!res.ok) return { state: "failed", status: res.status };
  return { state: "ok", data: await parse(res) };
}

// ## 三条各自发各自的 `fetch`，方法写成字面量
//
// 本来这三条共用一个 `call(path, method, …)`，方法当参数传。
// `tools/check_fe_api_contract.py` 当场报「路径在，但方法不允许（后端允许 DELETE）」——
// **它读的是 `fetch(` 那一处的方法字面量**，穿过一层 helper 之后它只看得见默认的 GET。
//
// 那把尺子是对的：方法藏在参数里时，**人读这份源码也一样看不出这条是删还是发**。
// 所以每条自己发，共用的只有上面那个「怎么读」。

/** 取消收藏。成功回 204，**没有正文**——所以 `data` 是 `null`。 */
export async function removeFavorite(
  favoriteId: string, opts: { baseUrl?: string; fetchImpl?: typeof fetch } = {},
): Promise<FavWriteResult<null>> {
  const f = opts.fetchImpl ?? fetch;
  const url = `${opts.baseUrl ?? API_BASE}/favorites/${encodeURIComponent(favoriteId)}`;
  let res: Response;
  try {
    res = await f(url, { method: "DELETE", headers: headers() });
  } catch {
    return { state: "failed", status: null };
  }
  return read(res, async () => null);
}

/** 把收藏的证据快照更新到最新。成功回**整条收藏**（含新快照）。 */
export async function refreshFavoriteSnapshot(
  favoriteId: string, opts: { baseUrl?: string; fetchImpl?: typeof fetch } = {},
): Promise<FavWriteResult<unknown>> {
  const f = opts.fetchImpl ?? fetch;
  // **URL 恒写在一行**：模板串里换一行，`check_fe_api_contract` 的路径扫描
  // 就在 `${` 处断掉，把这条读成 `/favorites/${`——于是它既报「这条端点没人调」，
  // 又报「前端在调一条后端没有的路」。实测撞过一次。
  const id = encodeURIComponent(favoriteId);
  const url = `${opts.baseUrl ?? API_BASE}/favorites/${id}/refresh-snapshot`;
  let res: Response;
  try {
    res = await f(url, { method: "POST", headers: headers() });
  } catch {
    return { state: "failed", status: null };
  }
  return read(res, (r) => r.json());
}

/** 问这一条旧没旧。**`not_checked` 是一等答案**，NEVER 折成 `false`。 */
export async function checkFavoriteStaleness(
  favoriteId: string, opts: { baseUrl?: string; fetchImpl?: typeof fetch } = {},
): Promise<FavWriteResult<StalenessAnswer>> {
  const f = opts.fetchImpl ?? fetch;
  const id = encodeURIComponent(favoriteId);
  const url = `${opts.baseUrl ?? API_BASE}/favorites/${id}/staleness`;
  let res: Response;
  try {
    res = await f(url, { method: "POST", headers: headers() });
  } catch {
    return { state: "failed", status: null };
  }
  return read(res, (r) => r.json() as Promise<StalenessAnswer>);
}
