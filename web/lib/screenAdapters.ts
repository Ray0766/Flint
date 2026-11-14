// WIRE-03：后端 JSON → 组件视图形状的适配层。
//
// ## 为什么需要它
//
// 两边**不是一个形状**，实测：
//
// | | 后端 | 组件视图 |
// |---|---|---|
// | 主体 | `principal: {kind, id}` | `principalId: string` |
// | 直属作用域 | `scopes.direct: {principal, role, via}` | `direct: {kind, id, role}` |
// | 没查过的列表 | `{"status": "not_checked"}`（**一个对象**） | `null` |
//
// 第三行是最要紧的一处：后端用**带 `status` 的对象**表示「没查过」
// （`BE-05/06` 的口径：连那个键都不给假数据），组件用 `null`。
// 两种表示法都自洽，但**不能不翻译直接喂**——不翻译的话
// `{"status":"not_checked"}` 会被组件当成一个真数组（真值），
// 于是「没查过」被渲染成「查过了、有内容」，正好是本批一路在治的那个错。
//
// 适配层只做**改形状**，NEVER 补默认值、NEVER 把缺的算出来：
// 后端没给的就是 `null`，让组件按它自己的三态去说。

import type { FavoriteFace, FavoriteItem } from
  "../components/favorites-library/FavoritesLibrary";
import type { AccountScope, AccountView } from
  "../components/account-billing/AccountPanel";
import type { BillingEventView, BillingView } from
  "../components/account-billing/BillingPanel";
import type { OverviewRow, ProjectOverviewView } from
  "../components/project-overview/ProjectOverview";

type Json = Record<string, unknown>;

function obj(value: unknown): Json {
  return value && typeof value === "object" ? (value as Json) : {};
}

/** 后端的「没查过」是一个 `{status:"not_checked"}` 对象；组件的是 `null`。 */
function checkedList<T>(value: unknown, key: string): T[] | null {
  const box = obj(value);
  if (box.status === "not_checked") return null;
  const items = box[key];
  return Array.isArray(items) ? (items as T[]) : null;
}

function scope(value: unknown): AccountScope {
  const row = obj(value);
  const principal = obj(row.principal);
  return {
    kind: principal.kind === "org" ? "org" : "user",
    id: String(principal.id ?? ""),
    role: String(row.role ?? ""),
  };
}

export function toAccountView(payload: unknown): AccountView {
  const body = obj(payload);
  const scopes = obj(body.scopes);
  return {
    principalId: String(obj(body.principal).id ?? ""),
    // `profile` 的判别联合两边逐字一致（`not_checked` / `no_record` / `known`），
    // 原样转出——**NEVER 在这里补一个 `no_record` 当默认值**。
    profile: obj(body.profile) as AccountView["profile"],
    memberships: checkedList<AccountScope>(scopes.memberships, "items")?.map(scope)
      ?? null,
    direct: scope(scopes.direct),
  };
}

/**
 * 项目总览：后端给的是**领域对象**，组件要的是三列 `{id, label, state}`。
 *
 * `WIRE-04` 的真栈取证把这一处抓了出来——第一版没写适配层，直接把后端 JSON
 * 喂给组件，于是 `key={row.id}` 全是 `undefined`，控制台一条
 * 「Each child in a list should have a unique key」。
 *
 * **传 `null` 的时候走不到那条渲染路径，所以之前一直看不见**：
 * 接上真数据才暴露。这正是本卡（逐屏真栈取证）存在的理由。
 */
export function toProjectOverviewView(payload: unknown): ProjectOverviewView {
  const body = obj(payload);
  const rows = (value: unknown, idKey: string, labelKeys: string[]): OverviewRow[] =>
    (Array.isArray(value) ? (value as Json[]) : []).map((row) => ({
      id: String(row[idKey] ?? ""),
      // 标题取第一个**非空**的候选键；一个都没有就退回 id，
      // NEVER 编一句「未命名」——那会让「没标题」和「标题就叫未命名」分不开。
      label: String(labelKeys.map((k) => row[k]).find((v) => v) ?? row[idKey] ?? ""),
      state: typeof row.status === "string" ? row.status : null,
    }));
  return {
    projectId: String(body.project_id ?? ""),
    // 后端没有单独的 title 字段，项目就用它的 id 标识——
    // 前端 NEVER 自己拼一个「项目 xxx 的总览」当标题。
    title: String(body.project_id ?? ""),
    topics: rows(body.topics, "topic_id", ["one_liner"]),
    jobs: rows(body.jobs, "job_id", ["kind"]),
    deliverables: rows(body.deliverables, "deliverable_id", ["kind", "title"]),
  };
}


export function toBillingView(payload: unknown): BillingView {
  const body = obj(payload);
  const events = checkedList<Json>(body.events, "items");
  return {
    billing: obj(body.billing) as BillingView["billing"],
    quota: obj(body.quota) as BillingView["quota"],
    events: events?.map((row): BillingEventView => ({
      jobId: String(row.job_id ?? ""),
      tier: String(row.tier ?? ""),
      at: String(row.at ?? ""),
      // 金额**恒是字符串**，原样转出，NEVER 转成 number 再格式化。
      amount: String(row.amount ?? ""),
      currency: String(row.currency ?? ""),
      pricingVersion: String(row.pricing_version ?? ""),
    })) ?? null,
    // 后端没给对账合计时就是「没查过」，NEVER 在前端自己加总
    // （前端零计算：合计是后端算好的一个字符串）。
    reconciliation: body.reconciliation === undefined || body.reconciliation === null
      ? null
      : {
        count: Number(obj(body.reconciliation).count ?? 0),
        total: String(obj(body.reconciliation).total ?? ""),
        mixedPricing: obj(body.reconciliation).mixed_pricing === true,
      },
  };
}

/**
 * 一份**真的有内容**的内嵌快照。
 *
 * `{}` 不算：空快照的收藏就是一个指向空处的壳，而那正是屏上
 * 「这条收藏的内容不在了」要说的事（后端 `add_favorite` 也拒它，`SCHEMA-09`）。
 */
function isNonEmptyObject(value: unknown): boolean {
  return (
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value) &&
    Object.keys(value as Record<string, unknown>).length > 0
  );
}

/**
 * `GET /favorites` → 组件的 `favorites` 入参（`WIRE-12`）。
 *
 * 后端此刻的两种答复**意思相反**：
 *
 * | 后端 | 意思 | 组件入参 |
 * |---|---|---|
 * | `{"status":"not_provided", ...}` | 这功能还没有库，**我们根本没查** | `null` |
 * | `{"items":[...]}` | 查过了，这是全部 | 那个数组（可以是 `[]`） |
 *
 * **NEVER 把第一种也翻成 `[]`**：屏上会写「还没有收藏」，
 * 而那是一句系统没有依据说出口的话。
 */
/**
 * 快照里的**卡面**（`FAV-CARD-01`）。
 *
 * 后端 `flint/fav/snapshot_source.py` 在收藏那一刻把它与证据卡一起存下：
 * `{cluster: {canonical_name, first_seen, region, heat}}`。
 *
 * 旧快照没有这一格（`FAV-SNAPSHOT` 那一版只存了证据卡）——
 * 那时回 `null`，屏上走既有的诚实态，**NEVER 编一个标题**。
 * 那些收藏按「更新到最新」就会拿到新形状。
 */
function cardFace(snapshot: unknown): FavoriteFace | null {
  if (!isNonEmptyObject(snapshot)) return null;
  const cluster = (snapshot as Record<string, unknown>).cluster;
  if (!isNonEmptyObject(cluster)) return null;
  const c = cluster as Record<string, unknown>;
  const name = typeof c.canonical_name === "string" ? c.canonical_name : "";
  if (!name) return null;
  return {
    nameNative: name,
    firstSeen: typeof c.first_seen === "string" ? c.first_seen : null,
    region: typeof c.region === "string" ? c.region : null,
    heat: typeof c.heat === "number" ? c.heat : null,
  };
}

export function toFavoritesView(payload: unknown): FavoriteItem[] | null {
  if (payload === null || typeof payload !== "object") return null;
  const box = payload as { status?: unknown; items?: unknown };
  if (box.status === "not_provided") return null;
  if (!Array.isArray(box.items)) return null;
  return box.items.map((raw) => {
    const row = raw as Record<string, unknown>;
    return {
      favoriteId: String(row.favorite_id ?? ""),
      targetKind: (row.target_kind ?? "cluster") as FavoriteItem["targetKind"],
      targetId: String(row.target_id ?? ""),
      // `SMOKE-01` 实测抓到：这里原先读的是 **`row.has_snapshot`——
      // 一个后端从来不发的字段**（`favorite_json` 回的是 `evidence_snapshot`）。
      // 于是 `Boolean(undefined)` 恒为 `false`，屏上每一条都说「内容不在了」——
      // **哪怕库里那份快照是完整的**。
      //
      // 这就是 `FAV-SNAPSHOT-HAS-NO-PROVIDER` 那张单上症状的第二个来源：
      // 快照真的曾经是空的（`DEC-055` 治的是那一半），
      // 而**即使不空，这一行也照样把它读成空**。
      //
      // 改成读**快照本身**：一处真相，NEVER 再要后端多发一个派生字段
      // ——多一个字段就多一处会对不上的地方（`AUDIT-01` 对账表反复抓的形状）。
      hasSnapshot: isNonEmptyObject(row.evidence_snapshot),
      // `FAV-CARD-01`：把快照里的**卡面**带过去，让收藏项能用与广场
      // 同一个 `HotspotCard` 渲染。改前这里只带了 `targetId`，
      // 于是屏上印的是裸簇 id（`c-20260810-002`）。
      //
      // 拿不到卡面时留 `null`——**NEVER 拿 targetId 顶上去当标题**：
      // 那正是今天这一屏的样子，而它看起来像「有内容」。
      face: cardFace(row.evidence_snapshot),
      stale: typeof row.snapshot_stale === "boolean" ? row.snapshot_stale : null,
    };
  });
}

