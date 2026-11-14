// GET /categories · flint/api/app.py#list_categories → flint/repo/categories.py
// 大类目录（12 类，assets/categories.yaml 播种，端点只读）。
//
// 这一支存在的意义：S0 外壳的大类筛选**必须**用真目录。
// 前端硬编码一份大类清单 = 造数据（技术约束清单第 2 条），NEVER 那样做；
// 端点取不到就如实标「端点未建 / 取不到」，让筛选器停用，也不假装有。

import type { Category } from "@/lib/types";
import { requestJson, type RequestOpts } from "./base";

export function fetchCategories(opts: RequestOpts = {}): Promise<Category[]> {
  return requestJson<Category[]>("/categories", opts);
}
