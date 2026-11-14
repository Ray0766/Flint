// 大类筛选（S0）· 数据来自 GET /categories，NEVER 前端硬编码目录。
//
// **行为契约（批次一字段对照表）**：筛选**仅隐藏行**，NEVER 重排。
// 主榜次序由后端 hotness 给定；隐藏若干行之后，剩下的行保持原有相对次序与原 rank 号。
// 实现方式是把选中的 category_id 写进 ?cat= ，由服务端页面据此过滤——
// 前端不持有第二份数据、不排序、不计算。
"use client";

import { useRouter, useSearchParams, usePathname } from "next/navigation";
import type { Category } from "@/lib/types";

export function CategoryFilter({
  categories,
  errored,
}: {
  categories: Category[] | null;
  errored: boolean;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const current = params.get("cat");

  // 目录取不到：停用并如实说明。NEVER 拿一份写死的清单顶上去。
  if (errored || categories === null) {
    return (
      <p className="font-mono text-[11px] text-ink-3">
        大类筛选不可用 · GET /categories 未返回目录（此处不代填清单）
      </p>
    );
  }
  if (categories.length === 0) {
    return (
      <p className="font-mono text-[11px] text-ink-3">
        大类目录为空数组 · 这是真实空态，非加载中
      </p>
    );
  }

  const go = (cat: string | null) => {
    const next = new URLSearchParams(params.toString());
    if (cat === null) next.delete("cat");
    else next.set("cat", cat);
    router.push(`${pathname}?${next.toString()}`);
  };

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="mr-1 font-mono text-[10px] uppercase tracking-[0.12em] text-ink-3">
        大类 · GET /categories
      </span>
      <button
        type="button"
        onClick={() => go(null)}
        aria-pressed={current === null}
        className={`border px-2.5 py-1 font-mono text-[11px] transition-colors ${
          current === null
            ? "border-ink bg-ink text-primary-foreground"
            : "border-rule text-ink-2 hover:border-rail"
        }`}
        style={{ borderRadius: "var(--radius)" }}
      >
        全部
      </button>
      {categories.map((c) => {
        const on = current === c.category_id;
        return (
          <button
            key={c.category_id}
            type="button"
            onClick={() => go(c.category_id)}
            aria-pressed={on}
            title={c.category_id}
            className={`border px-2.5 py-1 text-[11px] transition-colors ${
              on
                ? "border-ink bg-ink text-primary-foreground"
                : "border-rule text-ink-2 hover:border-rail"
            }`}
            style={{ borderRadius: "var(--radius)" }}
          >
            {c.name}
          </button>
        );
      })}
    </div>
  );
}
