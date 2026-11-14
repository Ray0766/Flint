// GET /plaza/hot?day=YYYY-MM-DD · flint/api/views.py#plaza
// 主榜 clusters（后端 compute_hotness 算好）+ 单列 weak_signals 弱信号轨。
// 前端零计算、零重排：后端已按 hotness 降序给定，原样渲染。

import type { PlazaHotResponse } from "@/lib/types";
import { requestJson, type RequestOpts } from "./base";

/** day 非 YYYY-MM-DD → 后端 400 VALIDATION_FAILED（不在前端预判，让后端说了算）。 */
export function fetchPlazaHot(day: string, opts: RequestOpts = {}): Promise<PlazaHotResponse> {
  return requestJson<PlazaHotResponse>(`/plaza/hot?day=${encodeURIComponent(day)}`, opts);
}
