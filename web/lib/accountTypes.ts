// TYPE-06：账户 / 计费 / 设计台 / 干预锁——五条端点的响应形状。
//
// ## 这五条为什么此前「根本没建类型」
//
// 与 `TYPE-05` 那七条不同：那七条被尺子**认错了接口**，这五条是真的一个都没有。
// `GAUGE-14` 修掉对账器两个盲区（首段白名单 + 只扫 `web/lib/`）之前，
// 这些调用点扫不到，**其响应类型自然无从比对**——
// 它们不是新引入的缺口，是第一次被看见。
//
// ## 这一族的形状有一条共同纪律：**四种「没有」互不合并**
//
// 后端在这五条上反复用同一组状态词，每一个说的都是不同的事（`DEC-032`）：
//
// | 值 | 它说的是 | 用户该做什么 |
// |---|---|---|
// | `not_checked` | **没查过**（数据源没注入） | 等 / 去接线 |
// | `no_record` | 查过了，库里没有这一条 | 去补资料 |
// | `not_enabled` | 能力在，但没配（计费未配置） | 去配 |
// | `not_provided` | **这一族还没有后端**（注册表不可用） | 等那张表建好 |
//
// 前端把它们折成一个 `null`，屏上就只剩「没有」两个字，
// 而这四件事要用户做的完全不同。所以这里**逐个建成判别联合**：
// 折叠会在 `tsc` 那一层就被拦下。

// ── `GET /account`（BE-05）：身份 / owner_scope / 角色，**NEVER 造第四样**

export interface AccountPrincipal {
  kind: string;
  id: string;
}

/** 档案三态。`no_record` 时 **NEVER 拿 id 拼一个显示名**——前端会把它当真名。 */
export type AccountProfile =
  | { status: "not_checked" }
  | { status: "no_record" }
  | {
      status: "known";
      display_name: string;
      email: string;
      /** ISO 时刻。 */
      created_at: string;
    };

/** 一条授权：直属（`direct`）或经成员关系（`membership`）。 */
export interface AccountScope {
  principal: AccountPrincipal;
  role: string;
  via: string;
}

export type AccountMemberships =
  | { status: "not_checked" }
  | { status: "checked"; items: AccountScope[] };

export interface AccountScopes {
  /** 归属直属那一条**恒成立**（个人使用无需先建 Org），且它不是一条 Membership 记录。 */
  direct: AccountScope;
  memberships: AccountMemberships;
}

export interface AccountResponse {
  principal: AccountPrincipal;
  profile: AccountProfile;
  scopes: AccountScopes;
}

// ── `GET /billing`（BE-06）：钱恒是**字符串**

/**
 * 计费配置三态。`not_enabled` 时 **NEVER 拿一个 0 元或一个假额度冒充已启用**。
 */
export type BillingConfigState =
  | { status: "not_enabled"; reason: string }
  | { status: "enabled"; currency: string; pricing_version: string };

/**
 * 额度四态。`remaining` / `exhausted` 都是**后端给的数**——
 * 前端零计算，NEVER 拿 `limit - used` 自己再判一次。
 */
export type QuotaState =
  | { status: "not_checked" }
  | { status: "not_enabled"; used: number }
  | {
      status: "enabled";
      used: number;
      limit: number;
      remaining: number;
      exhausted: boolean;
      shortfall: number;
    };

/** 一笔账的用量三态。`no_record` = 用量源串了行，**丢掉**而不是贴到这笔账上。 */
export type UsageState =
  | { status: "not_checked" }
  | { status: "no_record" }
  | {
      status: "known";
      call_count: number;
      input_tokens: number;
      output_tokens: number;
      cache_hit_tokens: number;
    };

export interface BillingEventRow {
  job_id: string;
  tier: string;
  /** ISO 时刻。 */
  at: string;
  /** **钱恒是字符串**：浮点会在对账时差出分。 */
  amount: string;
  currency: string;
  pricing_version: string;
  usage: UsageState;
}

export interface BillingReconciliation {
  count: number;
  /** 合计，同样是字符串。空账出 `"0"`，不是报错。 */
  total: string;
  currencies: string[];
  pricing_versions: string[];
  /** 两个版本的钱加在一起，那个和没有意义——**要报出来**。 */
  mixed_pricing: boolean;
}

/** 分支各自具名——**联合的成员写成匿名字面量时，对账器看不见它们的字段**
 *  （它只扫 `export interface`）。具名之后，`reconciliation` 这样只出现在
 *  一个分支里的字段才被算进「前端声明了」。 */
export interface BillingEventsNotChecked {
  status: string;
}

export interface BillingEventsChecked {
  status: string;
  items: BillingEventRow[];
  reconciliation: BillingReconciliation;
}

export type BillingEvents = BillingEventsNotChecked | BillingEventsChecked;

export interface BillingResponse {
  principal: AccountPrincipal;
  billing: BillingConfigState;
  quota: QuotaState;
  events: BillingEvents;
}

// ── `GET /design/templates`（DESIGN-03）

/** 一条模板的**元信息**。不回 `html`（渲染的事）、不回 `owner`（调用方就是 owner）。 */
export interface DesignTemplateRow {
  template_id: string;
  name: string;
  version: number;
  slots: string[];
  source_deliverable_id: string;
  checksum: string;
  /** ISO 时刻。 */
  solidified_at: string;
  enabled: boolean;
}

/**
 * `not_provided` = **模板还没有存储面**（迁移里没有 templates 表）。
 *
 * 后端明确地 NEVER 回 `{"items": []}`——空表与「查过了、你确实一个都没存」
 * 逐字相同，而真相是我们根本没查。这个联合让前端也没法把两者折在一起。
 */
export interface DesignTemplatesNotProvided {
  status: string;
  reason: string;
}

export interface DesignTemplatesList {
  items: DesignTemplateRow[];
}

export type DesignTemplatesResponse =
  | DesignTemplatesNotProvided
  | DesignTemplatesList;

/** 固化一份样板的回执。`accepted=false` 时 `reason` 说明为什么。 */
export interface DesignSolidifyResult {
  kind: string;
  template_id: string;
  accepted: boolean;
  reason: string | null;
}

/** 422 的机读体：拦下来的**完整清单**，不是第一条。 */
export interface DesignViolations {
  violations: string[];
}

// ── `GET /design/sessions/{id}/replay`（DESIGN-02）

export interface DesignReplayResponse {
  /** 重放拼出来的正文。 */
  text: string;
  seq: number;
  /** 真正落过盘的事件条数——**与 `seq` 不是一回事**（临时块不落盘）。 */
  replayed: number;
}

/** 409 的机读体：检查点没盖住的那几个 seq，**NEVER 悄悄放过**。 */
export interface DesignUncheckpointed {
  uncheckpointed_seqs: number[];
}

// ── `POST /interventions/lock`（M3-071）

/**
 * 锁一个块或一节。
 *
 * 端点成功时回 **204 无体**——`locked` 这个键出现在它写进
 * `EditEvent.after` 的那份记录里（对账器把处理函数里所有字面量 dict 的键
 * 都算作这条路由的键）。所以这里建的是**那条编辑事件的后像**，
 * **NEVER 编一个 `{ locked: true }` 的「响应」**：那种响应根本不存在，
 * 照它去读 `res.locked` 拿到的永远是 `undefined`。
 */
export interface LockEditAfter {
  locked: boolean;
}
