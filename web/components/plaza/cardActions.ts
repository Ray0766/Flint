"use client";

// PLAZA-04：卡片三动作的端点调用。
//
// ## 三条路今天各自走到哪（本卡开工时逐条打过真栈，不是读代码猜的）
//
// | 动作 | 端点 | 实测 | 屏上该说什么 |
// |---|---|---|---|
// | 收藏 | `POST /favorites` | `{"status":"not_provided","reason":"收藏还没有存储面…"}` | 接口未提供（`DEC-032`） |
// | 分享 | `POST /shares` | `422 {"allowed":["deliverable","graph","topic"]}` | 这类目标还不支持分享 + 服务端给的清单 |
// | 入台 | `POST /workbenches` | `201 {graph_id, …}`（`SMOKE-01` 实测挂着且能用） | 跳到那张图 |
//
// ## 为什么三种「不成」要分成三句话
//
// 「这个能力还没接」（收藏、入台）与「这个能力在，但热点不是它能收的东西」（分享）
// **是两件事**：前者等我们去挂，后者要改冻结件里的 `target_kind`。
// 混成一句「暂不可用」，用户与下一个读代码的人都无从知道该做什么。
// 这与本仓一路在守的「未知 ≠ 没查过 ≠ 没接」是同一条纪律。
//
// ## 为什么分享**照样把请求发出去**
//
// 「热点算不算可分享的目标」这件事的真相在服务端（冻结件的 `target_kind` 判别联合）。
// 前端自带一份清单去预判，那份清单会与冻结件各自漂移；
// 而 422 的 `detail.allowed` 是**服务端自己报出来的**，用它渲染那句话，永远不会说错。
//
// 收藏与入台不预判也不自带清单：**按答复说话**。
// （这一行原先写的是「它们的答复本身就是『没接』」—— 实测
//  两条今天都能用：收藏回 200、入台回 201。不预判那条纪律没变，变的是实况。）

import { API_USER_ID } from "../../lib/apiBase";

const NOT_PROVIDED = "not_provided";

export type ActionOutcome =
  /** 成功。今天三条路都到不了这里，但它 NEVER 被删——留着，接通那天不用改调用方。 */
  | { kind: "ok"; detail: Record<string, unknown> }
  /** 这个能力还没接（存储面缺失，或路由没挂）。 */
  | { kind: "not_provided"; reason: string }
  /** 能力在，但这类目标不在冻结件允许的清单里。`allowed` **来自服务端**。 */
  | { kind: "unsupported"; allowed: string[] }
  /** 别的失败。后端自己的说明原样带出来，NEVER 改写成一句通用的话。 */
  | { kind: "failed"; status: number; message: string };

type Json = Record<string, unknown>;

async function post(base: string, path: string, body: Json): Promise<ActionOutcome> {
  let res: Response;
  try {
    // 身份头从配置来（`API_USER_ID`）。**没配就不发**——发一个编出来的身份
    // 会让服务端把别人的数据当成你的（`FB-10` 的 A 类里 `X-User-Id` 逐字点名）。
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (API_USER_ID) headers["x-user-id"] = API_USER_ID;
    res = await fetch(`${base}${path}`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    });
  } catch (err: unknown) {
    return { kind: "failed", status: 0, message: String(err) };
  }
  const payload = (await res.json().catch(() => ({}))) as Json;

  if (payload["status"] === NOT_PROVIDED) {
    return { kind: "not_provided", reason: String(payload["reason"] ?? "") };
  }
  if (res.status === 422) {
    const detail = (payload["detail"] ?? {}) as Json;
    const allowed = Array.isArray(detail["allowed"]) ? (detail["allowed"] as string[]) : [];
    if (allowed.length > 0) return { kind: "unsupported", allowed };
  }
  // 框架的路由未命中回 `{"detail":"Not Found"}`——**没有 `code`**。
  // 带 `code` 的 404 是「这一条不存在」，没有 `code` 的 404 是「这个能力还没挂」。
  // 两者混成一句，用户会拿一个正确的 id 反复试（`NotFound404` 的既有口径）。
  if (res.status === 404 && payload["code"] === undefined) {
    return { kind: "not_provided", reason: String(payload["detail"] ?? "") };
  }
  if (!res.ok) {
    return {
      kind: "failed",
      status: res.status,
      message: String(payload["message"] ?? payload["detail"] ?? ""),
    };
  }
  return { kind: "ok", detail: payload };
}

/**
 * 收藏一个热点簇。`favorite_id` 由调用方给，服务端按它判重（同一条不会收两次）。
 *
 * ## 这里 NEVER 再送 `evidence_snapshot`
 *
 * 改前送的是 `{}`。广场这个动作手上只有热点卡面（id / 名称 / 热度），
 * **它拼不出真快照**——拼一份就是编一份证据（`FAV-WRITES` acceptance④ 逐字禁止）。
 * 于是每一条收藏都带着一份空快照存下去，而收藏屏上说「这条收藏的内容不在了」：
 * 那句是实话，**而真相是没有人往里面放东西**。
 *
 * `DEC-055`（owner 2026-08-10）：这一格改成可选，**后端在收藏那一刻自取**。
 * 前端只说「收哪一条」，NEVER 说「它的证据长什么样」。
 *
 * 取不着时后端回 **502 `EVIDENCE_FETCH_FAILED`** 且**不存**——
 * 那一句与「内容已被清理」NEVER 共用（一个能重试，一个重试一万次也回不来）。
 */
export function favoriteCluster(base: string, clusterId: string): Promise<ActionOutcome> {
  return post(base, "/favorites", {
    favorite_id: `fav-${clusterId}`,
    target_kind: "cluster",
    target_id: clusterId,
  });
}

/** 分享一个热点簇。目标类型合不合法**由服务端判**——前端不自带清单。 */
export function shareCluster(base: string, clusterId: string): Promise<ActionOutcome> {
  return post(base, "/shares", {
    target_kind: "cluster",
    target_id: clusterId,
    expires_at: null,
  });
}

/**
 * 入台：把这个热点带进图谱工作台。
 *
 * `POST /workbenches` **今天挂着且能用**（`SMOKE-01` 2026-08-11 实测：
 * 打过去回 `201 {graph_id, seed_cluster_id, created}`，随后
 * `GET /workbenches/{graph_id}` 读得回一张带那条热点的图）。
 *
 * 这里原先写的是「今天没挂（实测 404）」——**那句今天是假的**。
 * 它不影响这个函数的行为（本来就是「照样打它、按答复说话」），
 * 但照着它读的人会以为入台这一步没做。
 *
 * 照样打它、按答复说话那一条不变：**NEVER 前端自己跳到一个编出来的工作台 id**，
 * 跳过去会落进一个不存在的图谱，而用户会以为是自己的数据丢了。
 */
export function addToWorkbench(base: string, clusterId: string): Promise<ActionOutcome> {
  return post(base, "/workbenches", { seed_cluster_id: clusterId });
}

/**
 * NAV-03：入台成功之后要去的那个工作台是**哪一个**——`graph_id` 由服务端给。
 *
 * `graph_id` 是冻结件里的名字，也是既有路由 `POST /workbenches/{graph_id}/edges`
 * 用的那个。这里 NEVER 认第二个别名：认两个名字的话，服务端哪天改口，
 * 前端会安静地跳到另一处，而两边都以为自己对。
 *
 * 服务端没给就回 `null`，**调用方据此留在原地**。
 * 拿 `cluster_id` 拼一个跳过去，用户会落进一个不存在的图谱，
 * 并以为是自己的数据丢了（`addToWorkbench` 文件头的原话）。
 */
export function workbenchTarget(outcome: ActionOutcome): string | null {
  if (outcome.kind !== "ok") return null;
  const id = outcome.detail["graph_id"];
  return typeof id === "string" && id !== "" ? id : null;
}
