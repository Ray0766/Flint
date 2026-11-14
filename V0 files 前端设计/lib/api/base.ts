// 薄 API 客户端 · 公共层
//
// 对着**真端点**（harness/demo_server.py 合并挂载的 views + combo + analysis +
// deliverables app）。本层只做：拼 URL、发请求、把后端错误体原样抬起来。
// NEVER 在此改写/补全/兜底任何业务字段——缺什么就让上层如实显缺。
//
// 基址：NEXT_PUBLIC_FLINT_API（例 http://localhost:8000）。未设 → 用 DEFAULT_API_BASE，
// 并在 FlintNetworkError 里把用的是哪个基址讲清楚，避免"连不上还不知道连的谁"。

import type { ErrorBody } from "@/lib/types";

export const DEFAULT_API_BASE = "http://localhost:8000";

export const API_BASE: string =
  process.env.NEXT_PUBLIC_FLINT_API?.replace(/\/+$/, "") || DEFAULT_API_BASE;

// demo 后端有 X-User-Id 注入中间件（不发该头 → 注 demo-user）。这里仍显式带上，
// 使本客户端对**不注入**的部署同样成立；值可用 NEXT_PUBLIC_FLINT_USER_ID 覆盖。
// 注意：浏览器原生 EventSource 无法带自定义头，SSE 一路仍依赖后端注入。
export const USER_ID: string = process.env.NEXT_PUBLIC_FLINT_USER_ID || "demo-user";

/** 后端按契约回了错误体（4xx/5xx）。code/message/detail 原样保留供 UI 如实呈现。 */
export class FlintApiError extends Error {
  readonly status: number;
  readonly body: ErrorBody | null;
  readonly url: string;

  constructor(status: number, url: string, body: ErrorBody | null) {
    super(body?.message ?? `HTTP ${status} · ${url}`);
    this.name = "FlintApiError";
    this.status = status;
    this.url = url;
    this.body = body;
  }

  get code(): string {
    return this.body?.code ?? `HTTP_${this.status}`;
  }

  get blockingBlockIds(): string[] {
    return this.body?.detail?.blocking_block_ids ?? [];
  }

  /** 409 LEDGER_CONFLICT 时账本已前进到的版本；后端未携带则 null（NEVER 猜一个数）。 */
  get currentVersion(): number | null {
    const v = this.body?.detail?.current_version;
    return typeof v === "number" ? v : null;
  }
}

/** 根本没连上后端（进程没起 / 端口不通 / DNS）。与"后端回了错"是两种态，分开显。 */
export class FlintNetworkError extends Error {
  readonly url: string;
  readonly base: string;

  constructor(url: string, cause: unknown) {
    super(`无法连接后端：${url}`);
    this.name = "FlintNetworkError";
    this.url = url;
    this.base = API_BASE;
    this.cause = cause;
  }
}

export interface RequestOpts {
  /** 注入用（测试/story）；缺省走全局 fetch。 */
  fetchImpl?: typeof fetch;
  signal?: AbortSignal;
  method?: string;
  body?: unknown;
  /** 额外头（如 Idempotency-Key）。 */
  headers?: Record<string, string>;
}

export function apiUrl(path: string): string {
  return `${API_BASE}${path}`;
}

async function parseErrorBody(res: Response): Promise<ErrorBody | null> {
  try {
    const parsed: unknown = await res.json();
    if (parsed && typeof parsed === "object" && "code" in parsed) {
      return parsed as ErrorBody;
    }
    // FastAPI 校验错误（422）等非契约体：包成同形，message 保留原文。
    return { code: `HTTP_${res.status}`, message: JSON.stringify(parsed), detail: null };
  } catch {
    return null;
  }
}

/** 发请求 → 200 回解析后的 JSON；非 2xx 抛 FlintApiError；连不上抛 FlintNetworkError。 */
export async function requestJson<T>(path: string, opts: RequestOpts = {}): Promise<T> {
  const res = await rawRequest(path, opts);
  if (!res.ok) throw new FlintApiError(res.status, apiUrl(path), await parseErrorBody(res));
  return (await res.json()) as T;
}

/** 只要 Response 本体（导出下载/二进制走这条）。非 2xx 同样抛 FlintApiError。 */
export async function requestOk(path: string, opts: RequestOpts = {}): Promise<Response> {
  const res = await rawRequest(path, opts);
  if (!res.ok) throw new FlintApiError(res.status, apiUrl(path), await parseErrorBody(res));
  return res;
}

async function rawRequest(path: string, opts: RequestOpts): Promise<Response> {
  const url = apiUrl(path);
  const f = opts.fetchImpl ?? fetch;
  const headers: Record<string, string> = { "x-user-id": USER_ID, ...opts.headers };
  if (opts.body !== undefined) headers["content-type"] = "application/json";
  try {
    return await f(url, {
      method: opts.method ?? "GET",
      headers,
      body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
      signal: opts.signal,
      // demo 是活数据（热点日更 / job 进行中）：一律现读，NEVER 让缓存把旧态当新态显。
      cache: "no-store",
    });
  } catch (cause) {
    throw new FlintNetworkError(url, cause);
  }
}

/** 404 → null（"尚未生成"是正常业务态，不是错误）；其余错误照抛。 */
export async function requestJsonOrNull<T>(
  path: string,
  opts: RequestOpts = {},
): Promise<T | null> {
  try {
    return await requestJson<T>(path, opts);
  } catch (err) {
    if (err instanceof FlintApiError && err.status === 404) return null;
    throw err;
  }
}
