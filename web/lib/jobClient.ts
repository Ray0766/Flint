// L1 Job + SSE 渐进交付客户端。冻结件 contracts/models.py 的 JobState /
// JobEventPayload 判别联合 TS 镜像。只读消费，NEVER 回写。
// 后端：POST /projects/{id}/{analysis|report|proposal} → {job_id}；
// GET /jobs/{id} 状态；GET /jobs/{id}/events SSE（id=seq，data=payload JSON，
// Last-Event-ID 续订——浏览器原生 EventSource 自动带头 + 重连）。

export type JobState =
  | "queued" | "retrieving" | "judging" | "drafting"
  | "validating" | "done" | "failed" | "cancelled";

export interface StatusChanged { kind: "status"; state: JobState; }
export interface StepEvent { kind: "step"; step_name: string; phase: "start" | "end"; cost: number | null; }
export interface PartialBlockEvent { kind: "partial_block"; block_id: string; }
export interface JobFailedEvent { kind: "failed"; reason: string; }
/**
 * 设计台的流式增量块（`contracts_v04` 的 §9-P3）。
 *
 * **DESIGN-02 补的**：这份镜像自述是「冻结件判别联合的 TS 镜像」，而它一直少这一个成员。
 * 代价不是「少显示一点」——`applyEvent` 结尾是 `assertNever`，
 * 真来一条 `design_delta` 会**当场抛**，整条流断在那里，
 * 而屏上看起来只是「不再有新内容了」。
 */
export interface DesignDeltaEvent { kind: "design_delta"; seq: number; fragment: string; }
export type JobEventPayload =
  | StatusChanged | StepEvent | PartialBlockEvent | JobFailedEvent | DesignDeltaEvent;

export const TERMINAL_STATES: Set<JobState> = new Set(["done", "failed", "cancelled"]);

export type JobKind = "analysis" | "report" | "proposal";

export interface JobStreamState {
  /** 作业自己的状态（后端发来的）。 */
  status: JobState | null;
  /**
   * **连接**的状态——与作业的状态是两回事。
   *
   * `UIX-02` 补：此前没有这个字段，`onerror` 也从未被赋值，
   * 于是后端挂掉时屏上一个字都不变，用户把停住的旧数据读成「还在跑」。
   *
   * `disconnected` 是**可恢复态**：原生 `EventSource` 会自动重连，
   * 下一条消息到达时要回到 `open`——NEVER 卡死在断线态。
   */
  connection: "connecting" | "open" | "disconnected";
  /**
   * **能不能看**——与「连不上」是两回事（`UIX-04`）。
   *
   * 改前没有这个字段：`EventSource` 的 `onerror` **不带 HTTP 状态**，
   * 于是 403 与断网在屏上长得一模一样，作业屏卡在一张**永远转下去的骨架**上。
   * 而两者要用户做的事完全相反：一个是继续等，一个是去要权限。
   *
   * - `unknown` = 还没探过，或探出来是别的失败（500 / 真断网）。
   *   **NEVER 把它说成「无权」**：那会让用户去要一个他本来就有的权限。
   * - `unauthenticated`（401）= 「你是谁」的问题 → 去登录；
   * - `denied`（403）= 「你能干什么」的问题 → 去要权限。
   *   两者分开是 `AUTH-03` 的口径，并成一句用户就不知道下一步做什么。
   *
   * **刻意不塞进 `connection`**：塞进去，「不让你连」就成了「连接的一种状态」，
   * 而它其实是**答案已经给了**——重连一万次也还是 403。
   */
  access: "unknown" | "unauthenticated" | "denied";
  steps: StepEvent[];
  arrivedBlockIds: string[];
  failedReason: string | null;
  /**
   * 设计台逐块拼起来的文字。**拼接只有这一处实现**——
   * 屏那边再拼一次的话，两处的拼法会在某个边界上分叉（丢块、重块都看不出来）。
   */
  designText: string;
  lastEventId: number | null;
  done: boolean;
}

export const initialJobStreamState: JobStreamState = {
  status: null,
  connection: "connecting",
  access: "unknown",
  steps: [],
  arrivedBlockIds: [],
  failedReason: null,
  designText: "",
  lastEventId: null,
  done: false,
};

// 纯归约器：seq 去重（断线续订重放 seq<=lastEventId 一律忽略，防重复挂载）。
export function applyEvent(
  state: JobStreamState,
  id: string,
  payload: JobEventPayload,
): JobStreamState {
  const seq = Number(id);
  if (state.lastEventId !== null && seq <= state.lastEventId) {
    return state; // 已见 seq：续订重放，幂等忽略
  }
  const next: JobStreamState = { ...state, lastEventId: seq };
  switch (payload.kind) {
    case "status":
      next.status = payload.state;
      if (TERMINAL_STATES.has(payload.state)) next.done = true;
      return next;
    case "step":
      next.steps = [...state.steps, payload];
      return next;
    case "partial_block":
      next.arrivedBlockIds = state.arrivedBlockIds.includes(payload.block_id)
        ? state.arrivedBlockIds
        : [...state.arrivedBlockIds, payload.block_id];
      return next;
    case "failed":
      next.failedReason = payload.reason;
      // `UIR-02`：失败事件自己就说明了状态。这里一置 `done`，流就关了，
      // 后面那条 `status/failed` 读不到——不在这里写，状态那一格会停在上一个中间态。
      next.status = "failed";
      next.done = true;
      return next;
    case "design_delta":
      // seq 去重在函数开头已经做过（`seq <= lastEventId` 一律忽略），
      // 所以这里直接拼——断线续订重放的那几块 NEVER 被拼第二遍。
      next.designText = state.designText + payload.fragment;
      return next;
    default:
      return assertNever(payload);
  }
}

export interface SubmitOpts {
  userId: string;
  idempotencyKey?: string;
  baseUrl?: string;
  fetchImpl?: typeof fetch;
}

export async function submitJob(
  projectId: string,
  kind: JobKind,
  body: unknown,
  opts: SubmitOpts,
): Promise<string> {
  const f = opts.fetchImpl ?? fetch;
  const headers: Record<string, string> = {
    "content-type": "application/json",
    "x-user-id": opts.userId,
  };
  if (opts.idempotencyKey) headers["idempotency-key"] = opts.idempotencyKey;
  const res = await f(
    `${opts.baseUrl ?? ""}/projects/${encodeURIComponent(projectId)}/${kind}`,
    { method: "POST", headers, body: JSON.stringify(body) },
  );
  if (!res.ok) throw new Error(`submitJob ${kind}: HTTP ${res.status}`);
  const data = (await res.json()) as { job_id: string };
  return data.job_id;
}

export async function fetchJobSnapshot(
  jobId: string,
  opts: { userId: string; baseUrl?: string; fetchImpl?: typeof fetch },
): Promise<{ state: JobState }> {
  const f = opts.fetchImpl ?? fetch;
  const res = await f(`${opts.baseUrl ?? ""}/jobs/${encodeURIComponent(jobId)}`, {
    headers: { "x-user-id": opts.userId },
  });
  if (!res.ok) throw new Error(`fetchJobSnapshot ${jobId}: HTTP ${res.status}`);
  return (await res.json()) as { state: JobState };
}

/**
 * 流出错之后**探一次**：到底是连不上，还是不让你连（`UIX-04`）。
 *
 * 原生 `EventSource` 的 `onerror` 不带 HTTP 状态，所以走 `fetch GET /jobs/{id}`——
 * 那条路读得到状态码，而且它与 SSE 那条**受同一条鉴权**（实测两条都回 403）。
 *
 * **探一次，不轮询**：轮询会在真断网时对着一个连不上的后端反复打，
 * 而屏上那句话不会因为多打几次变得更准。
 *
 * 探不出来就是 `unknown`——**NEVER 猜成 denied**：
 * 猜错会让用户去要一个他本来就有的权限，而真正的问题在后端。
 */
export async function probeJobAccess(
  jobId: string,
  opts: { baseUrl?: string; fetchImpl?: typeof fetch; userId?: string } = {},
): Promise<JobStreamState["access"]> {
  const f = opts.fetchImpl ?? fetch;
  const headers: Record<string, string> = {};
  if (opts.userId) headers["x-user-id"] = opts.userId;
  let status: number;
  try {
    const res = await f(
      `${opts.baseUrl ?? ""}/jobs/${encodeURIComponent(jobId)}`, { headers });
    status = res.status;
  } catch {
    // 连 fetch 都发不出去 = 真的断网。那不是「无权」。
    return "unknown";
  }
  // 401 与 403 **落在两个分支上**，NEVER 写进同一个条件（`AUTH-03`）：
  // 401 是「你是谁」→ 去登录；403 是「你能干什么」→ 去要权限。
  if (status === 401) return "unauthenticated";
  if (status === 403) return "denied";
  return "unknown";
}

interface MinimalEventSource {
  onmessage: ((e: { data: string; lastEventId: string }) => void) | null;
  onerror: ((e: unknown) => void) | null;
  close(): void;
}

export function openJobStream(
  jobId: string,
  onState: (state: JobStreamState) => void,
  opts: {
    EventSourceImpl?: typeof EventSource;
    baseUrl?: string;
    /** `probeJobAccess` 用（`UIX-04`）：判据要注入一个会回 403 的 fetch。 */
    fetchImpl?: typeof fetch;
    userId?: string;
  } = {},
): () => void {
  const ES = (opts.EventSourceImpl ?? EventSource) as unknown as new (
    url: string,
  ) => MinimalEventSource;
  const es = new ES(`${opts.baseUrl ?? ""}/jobs/${encodeURIComponent(jobId)}/events`);
  let state = initialJobStreamState;
  es.onmessage = (e) => {
    const payload = JSON.parse(e.data) as JobEventPayload;
    state = applyEvent(state, e.lastEventId, payload);
    // 收到消息 = 连接是通的。**重连成功要能自己回到 open**，
    // NEVER 卡死在断线态（`UIX-02`）。
    state = { ...state, connection: "open" };
    onState(state);
    if (state.done) es.close(); // 终态：停止订阅（原生 ES 否则会重连）
  };
  let probed = false;
  es.onerror = () => {
    // **只标连接断了，NEVER 碰 `failedReason`**：
    // 那是后端明确发来的「作业失败」，与「我们收不到消息了」是两件事。
    // 也 NEVER `close()`：原生 EventSource 正在自动重连，关掉就真断了。
    state = { ...state, connection: "disconnected" };
    onState(state);
    // UIX-04：**探一次**能不能看。放在标断线之后，因为断线是当下的事实；
    // 探出 403 之后屏上换成「无权查看」，而**那一句会盖住断线提示**——
    // 劝一个 403 的用户「稍后重试」是假话，重试永远不会成功。
    if (probed) return;
    probed = true;
    void probeJobAccess(jobId, opts).then((access) => {
      if (access === "unknown") return;   // 探不出来就什么都不改
      state = { ...state, access };
      onState(state);
    });
  };
  return () => es.close();
}

function assertNever(x: never): never {
  throw new Error(`unhandled job event payload: ${JSON.stringify(x)}`);
}
