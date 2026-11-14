// UI-02 导出屏的取数客户端。与屏同目录（Next 的 colocation 约定），
// 因为它只服务这一屏；放进 `lib/` 会让人以为别处也在用它。
//
// ## 三种结局各有各的形状，NEVER 合成一句「导出失败」
//
// | 后端 | 机器码 | 用户该看到什么 |
// |---|---|---|
// | 409 | `EXPORT_BLOCKED` | **哪些块**挡住了导出——那是他要去处理的清单 |
// | 503 | `SERVICE_UNAVAILABLE` | 这个格式暂时不可用，换别的格式（不转圈、不伪装下载） |
// | 其他非 2xx | —— | 如实报状态码 |
//
// 合成一句通用报错的代价：用户不知道该点哪儿。409 是**他能自己解决**的，
// 503 是**他等就行**的，两者混在一起就都变成了「不知道该怎么办」。

/** 后端 `_error` 的错误体形状（`flint/api/schemas.py#ErrorBody`）。 */
export interface ErrorBody {
  code: string;
  message: string;
  detail?: { blocking_block_ids?: string[]; violations?: string[] };
}

export type ExportFormat = "markdown" | "html" | "pdf" | "docx" | "pack";

/** 导出的结局。判别联合：读的人一眼看得出有几种收场。 */
export type ExportOutcome =
  | { kind: "ok"; fmt: ExportFormat; contentType: string }
  | { kind: "blocked"; fmt: ExportFormat; blockingBlockIds: string[]; violations: string[] }
  | { kind: "unavailable"; fmt: ExportFormat; message: string }
  | { kind: "failed"; fmt: ExportFormat; status: number };

export interface ExportOpts {
  baseUrl?: string;
  fetchImpl?: typeof fetch;
}

export async function requestExport(
  deliverableId: string,
  fmt: ExportFormat,
  opts: ExportOpts = {},
): Promise<ExportOutcome> {
  const f = opts.fetchImpl ?? fetch;
  const res = await f(
    `${opts.baseUrl ?? ""}/deliverables/${encodeURIComponent(deliverableId)}` +
      `/render?fmt=${encodeURIComponent(fmt)}`,
  );
  if (res.ok) {
    return { kind: "ok", fmt, contentType: res.headers.get("content-type") ?? "" };
  }
  if (res.status === 409 || res.status === 503) {
    // 错误体读不动时**不猜**：当成 failed 如实报状态码。猜一份 detail 出来，
    // 屏上就会列出一串不存在的 block id，而用户会真的去找它们。
    let body: ErrorBody | null = null;
    try {
      body = (await res.json()) as ErrorBody;
    } catch {
      body = null;
    }
    if (res.status === 409 && body?.code === "EXPORT_BLOCKED") {
      return {
        kind: "blocked",
        fmt,
        blockingBlockIds: body.detail?.blocking_block_ids ?? [],
        violations: body.detail?.violations ?? [],
      };
    }
    // 503 也按**机器码**认，NEVER 只看状态码：反代或网关也会发 503，
    // 那种 503 不是「这个格式暂时没接上」，把它说成后者会让用户一直等下去。
    if (res.status === 503 && body?.code === "SERVICE_UNAVAILABLE") {
      return { kind: "unavailable", fmt, message: body.message };
    }
  }
  return { kind: "failed", fmt, status: res.status };
}
