// WIRE-03：九张屏切真数据用的取数件。
//
// ## 为什么不是「返回数据或 null」
//
// 组件的入参是 `View | null`，`null` 渲染成「接口未提供」。
// 若取数件只会给出「数据」或「null」，那么**请求还在路上**的那一刻也是 null——
// 屏上会写「接口未提供」，而真相是「正在查」。
//
// 第 2 批钉了一整批的那条纪律在这里第三次出现：
// **「没查过」与「查过了、是空的／坏的」NEVER 挤进同一个表示。**
// 加上「正在查」和「查了、后端说它没配」，一共四种，各有各的名字。
//
// | 结果 | 什么意思 | 屏上该显示 |
// |---|---|---|
// | `loading` | 请求在路上 | 「正在查」——**NEVER 空态、NEVER 未提供** |
// | `ready` | 200，拿到了 | 真数据（空数组就是真的空） |
// | `not_found` | 带 `code` 的 404 | 「这一条不存在」——**这个能力在**，查了，没有这一条 |
// | `not_provided` | 路由未命中（框架的 404） | 「接口未提供」——**这个能力还没接** |
// | `not_configured` | 503 `FAMILY_NOT_CONFIGURED` | 「这一族还没有后端」——**不是坏了** |
// | `failed` | 其余非 2xx / 网络错 | 「出错了」+ 原样带出状态码 |
//
// `not_provided` 与 `not_configured` 分开，是因为它们要人做的事不同：
// 前者是「这条路由没挂上」，后者是「挂上了，但它背后没有库」。
//
// ## `FIX-11` 补的那一态
//
// 改前带 `code` 的 404 掉进 `failed`，屏上于是写「取数出错 · 后端回了一个错误状态」——
// **「这一条不存在」被说成「系统出错了」**。两者要人做的事完全不同：
// 前者换一个 id 或回上一层，后者等一会儿再试或来找我们。
// `NotFound404` 组件 `UIX-02` 就建好了，**因为这一态不存在而一直用不上**。
//
// `not_found` 带上后端自己的 `code` 与 `message`：屏上只说一句自己编的「找不到」
// 是不够的——`BE-09` 把**无权**与**不存在**收进同一条路（分开说等于告诉未授权的人
// 这个 id 存在），所以那句话得由后端来说。

export type Fetched<T> =
  | { kind: "loading" }
  | { kind: "ready"; data: T }
  | { kind: "not_found"; code: string; detail: string }
  | { kind: "not_provided" }
  | { kind: "not_configured"; family: string }
  | { kind: "failed"; status: number; detail: string };

export interface FetchOpts {
  baseUrl?: string;
  fetchImpl?: typeof fetch;
}

// **前端不发身份头。** 第一版这里有个 `userId?` 选项，但一张屏都没传过它——
// 而 `web/` 里出现一个「演示账号」形状的东西，`test_no_scaffold` 会当场判红，
// 那把尺子是对的：身份该由网关/中间件定，NEVER 由前端自己编一个。
// demo 栈的 `_InjectUserMiddleware` 在没有该头时注 `demo-user`。

/**
 * 取一条只读端点，把 HTTP 结果翻译成上表那五种之一。
 *
 * **NEVER 把 404 一律当成「接口未提供」**：本仓所有应用自己发的 404 都带
 * `code`（`BE-09` 的「404 不 403」口径就是这么发的），而框架的路由未命中
 * 回的是 `{"detail":"Not Found"}`。两者意思相反——
 * 前者是「挂上了，它说这东西不存在」，后者是「这条路由不在」。
 */
export async function fetchScreen<T>(
  path: string,
  opts: FetchOpts = {},
): Promise<Exclude<Fetched<T>, { kind: "loading" }>> {
  const f = opts.fetchImpl ?? fetch;
  let res: Response;
  try {
    res = await f(`${opts.baseUrl ?? ""}${path}`);
  } catch (err) {
    return { kind: "failed", status: 0, detail: String(err) };
  }
  if (res.ok) {
    return { kind: "ready", data: (await res.json()) as T };
  }
  let body: Record<string, unknown> = {};
  try {
    body = (await res.json()) as Record<string, unknown>;
  } catch {
    body = {};
  }
  if (res.status === 404 && typeof body.code === "string") {
    // 应用自己发的 404：这个能力在，它说这一条不存在（或你无权看，`BE-09` 同一条路）。
    return {
      kind: "not_found",
      code: body.code,
      detail: typeof body.message === "string" ? body.message : res.statusText,
    };
  }
  if (res.status === 404 && typeof body.code !== "string") {
    // 框架的路由未命中：这条路由不在。**与上一支意思相反**，NEVER 合并。
    return { kind: "not_provided" };
  }
  if (res.status === 503 && body.code === "FAMILY_NOT_CONFIGURED") {
    return { kind: "not_configured", family: String(body.family ?? "") };
  }
  return {
    kind: "failed",
    status: res.status,
    detail: typeof body.message === "string" ? body.message : res.statusText,
  };
}
