// S0 应用外壳 —— 批次一全部数据屏共用的顶栏。
//
// 组成：wordmark + 导航 + 大类筛选（GET /categories）+ 用户位（X-User-Id 占位）。
//
// 视觉：数据屏语言（日夜双主题，全部走语义 token）。
//   NEVER glow（那是首页营销屏专属，已圈在 .dark 作用域）；
//   NEVER --sulfur（黄底 CTA 只属营销屏——数据屏用它会稀释告警色的唯一性）。
//
// 诚实纪律：
// - 用户位没有账户端点（§3.9）→ 明写「账户端点未建」，X-User-Id 取自 lib/api 的真实常量，
//   NEVER 画一个看起来能点的头像菜单。
// - 大类筛选取不到目录时 → 停用并如实标注，NEVER 前端硬编码一份大类清单顶上。
import Link from "next/link";
import { USER_ID } from "@/lib/api";
import type { Category } from "@/lib/types";
import { ThemeToggle } from "@/components/theme-toggle";
import { CategoryFilter } from "@/components/shell/category-filter";

// 路由为设计决策（仓库原无正式路由），见批次一字段对照表。
const NAV = [
  { href: "/plaza", label: "热点广场" },
  { href: "/combo/new", label: "combo 入口" },
  { href: "/how-it-works", label: "它怎么工作" },
] as const;

export function AppShell({
  active,
  endpoint,
  categories,
  categoriesError,
  children,
}: {
  active?: string;
  /** 本屏读的真端点，等宽显示在顶栏下方，让「这屏的数据哪来的」一直可见 */
  endpoint?: string;
  /** null = 目录取不到（筛选停用并标注）；undefined = 本屏不需要筛选 */
  categories?: Category[] | null;
  categoriesError?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-svh bg-background text-foreground">
      <header className="border-b border-rule">
        <div className="mx-auto flex max-w-[1180px] flex-wrap items-center gap-x-6 gap-y-3 px-5 py-4">
          <Link href="/" className="font-display text-[20px] text-ink">
            Flint 燧石
          </Link>

          <nav className="flex items-center gap-4">
            {NAV.map((n) => (
              <Link
                key={n.href}
                href={n.href}
                aria-current={active === n.href ? "page" : undefined}
                className={
                  active === n.href
                    ? "text-[14px] font-medium text-ink"
                    : "text-[14px] text-ink-2 transition-colors hover:text-ink"
                }
              >
                {n.label}
              </Link>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-3">
            {/* 用户位：无账户端点，占位并明示（§3.9） */}
            <span
              className="hidden items-center gap-2 border border-rule px-2.5 py-1.5 sm:inline-flex"
              style={{ borderRadius: "var(--radius)" }}
              title="账户端点未建（§3.9）"
            >
              <span className="font-mono text-[11px] text-ink-3">X-User-Id</span>
              <span className="tabular font-mono text-[11px] text-ink-2">{USER_ID}</span>
              <span className="font-mono text-[10px] text-ink-3">· 账户端点未建</span>
            </span>
            <ThemeToggle />
          </div>
        </div>

        {(endpoint !== undefined || categories !== undefined) && (
          <div className="border-t border-rule bg-raised">
            <div className="mx-auto flex max-w-[1180px] flex-wrap items-center gap-x-6 gap-y-3 px-5 py-3">
              {endpoint !== undefined && (
                <code className="break-all text-[11px] text-ink-3">{endpoint}</code>
              )}
              {categories !== undefined && (
                <div className="ml-auto">
                  <CategoryFilter categories={categories} errored={categoriesError === true} />
                </div>
              )}
            </div>
          </div>
        )}
      </header>

      {children}
    </div>
  );
}
