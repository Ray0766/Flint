import type { CSSProperties } from "react"
import Link from "next/link"
import { ThemeToggle } from "@/components/theme-toggle"

/* ============================================================
   燧石 Flint · 营销首屏 (app/page.tsx)

   双主题：
   - 日间 = 纸感 landing（取自 前端设计/Lumina landing + 3D carousel「Flint 首页」）：
     大标题 + 克制留白 + 硫磺黄底 CTA。**NEVER 用 glow**——光晕压在浅底上会糊成脏污。
   - 夜间 = 已建的 glow 版（40px 圆角 / 8px 渐变描边 / 45px 光晕）。
   两者由 .glow-* 与 .accent-word 在 globals.css 里按 .dark 作用域自动切换，
   本文件不写任何主题分支逻辑、不写死颜色。

   信息架构（本轮精简）：导航 + hero + 少量证据点 + CTA + 页脚。
   原「13 步旅程」与「字段对照表」已迁往 /how-it-works（首页从 4100px 收缩）。

   数据诚实：
   - hero 判定卡每个值取自本机录制回放真跑的引擎产出
     （harness/gate1_live.py replay-qwen → snap-job-gate1-live-qwen-verdict），
     屏上标注出处与「非实时」，NEVER 冒充实时数据。
   - 全屏 NEVER 出现无出处统计数、NEVER 把布尔/枚举画成进度条或百分比。
   - 告警色 --spark 在本屏零出现：它只属于 blocking / 409 / 503。
   - 页脚站点图（owner 裁决 ④）：**未建的条目整条不列**。不展示 ≠ 声称不存在；
     等功能建好再加回来。故这里只出现真实可达的路由，NEVER 假链接、NEVER 「未建」标记堆在首屏。
   ============================================================ */

// —— hero 判定卡：真实引擎产出（录制回放），逐字段照抄快照，前端零判定 ——
const VERDICT_SAMPLE = {
  verdict: "D_insufficient",
  label: "暂无法判定",
  gaps: [
    { missing_what: "证伪检索相关率未达 θ_rel", action: "search" },
    { missing_what: "竞品扫描覆盖未达标（not_saturated）", action: "search" },
    { missing_what: "关键证据对齐未过（绝不带病判定）", action: "upload" },
    { missing_what: "竞品规模与定价确认：LightRAG、graphrag", action: "ask_user" },
  ],
  competitors: [
    { name: "LightRAG", strength: "unknown" },
    { name: "graphrag", strength: "unknown" },
  ],
} as const

// —— 少量证据点：每条都能指回真端点/真产物，NEVER 摆无出处的营销数字 ——
const PROOF_POINTS = [
  {
    k: "四源日更",
    v: "gtrends · weibo · ghtrend · arxiv",
    note: "GET /plaza/hot?day= 按源分列，前端零重排",
  },
  {
    k: "判定四分类",
    v: "A / B / C / D",
    note: "GET /jobs/{id}/verdict 直取后端档位，前端不判定",
  },
  {
    k: "结论必有引用",
    v: "账本外事实即拒稿",
    note: "组稿通道门校验每个 block 的 fact_ids 在账本内",
  },
  {
    k: "导出由后端把关",
    v: "409 EXPORT_BLOCKED",
    note: "存在 blocking 块时后端拒导出，前端不预判",
  },
] as const

// 页脚站点图（owner 裁决 ④）：**未建的条目整条不列**，而不是列出来标「未建」。
// 不展示 ≠ 声称不存在；等功能建好再把条目加回来。
// 因此这里只允许出现**真实可达**的路由——新增条目前先确认它真的存在。
const SITEMAP = [
  {
    group: "探索 · DISCOVER",
    links: [
      { label: "它怎么工作", href: "/how-it-works" },
      { label: "每日线索（广场）", href: "/plaza" },
      { label: "combo 入口", href: "/combo/new" },
      { label: "样例报告", href: "/deliverables/del-demo-fixture-report" },
    ],
  },
] as const

function enter(i: number): CSSProperties {
  return { "--enter-delay": `${i * 90}ms` } as CSSProperties
}

function Nav() {
  return (
    <header className="border-b border-rule">
      <div className="mx-auto flex max-w-[1180px] items-center justify-between gap-4 px-6 py-5">
        <span className="font-display text-[22px] text-ink">Flint 燧石</span>
        <nav className="flex items-center gap-5">
          <Link href="/how-it-works" className="text-[14px] text-ink-2 transition-colors hover:text-ink">
            它怎么工作
          </Link>
          <Link href="/plaza" className="hidden text-[14px] text-ink-2 transition-colors hover:text-ink sm:inline">
            每日线索
          </Link>
          <ThemeToggle />
        </nav>
      </div>
    </header>
  )
}

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-foreground">
      <Nav />

      {/* ============ HERO ============ */}
      <section className="relative overflow-hidden">
        {/* 背景辉光：仅夜间显示（.glow-bloom 在日间为 display:none） */}
        <div
          className="glow-bloom left-[-10%] top-[-12%] h-[520px] w-[520px] opacity-[0.16]"
          style={{ background: "var(--glow-1)" }}
          aria-hidden
        />
        <div
          className="glow-bloom right-[-8%] top-[18%] h-[460px] w-[460px] opacity-[0.13]"
          style={{ background: "var(--glow-2)" }}
          aria-hidden
        />

        <div className="relative z-[2] mx-auto grid max-w-[1180px] items-center gap-14 px-6 py-20 md:grid-cols-[1.05fr_minmax(0,460px)] md:py-28">
          <div className="flex flex-col">
            <div
              className="enter mb-7 flex items-center gap-3 font-mono text-[11px] uppercase tracking-[0.18em] text-ink-3"
              style={enter(0)}
            >
              <span>FLINT · DAILY</span>
              <span className="h-px w-8 bg-rail" />
              <span>每日热点，敲成报告</span>
            </div>

            <h1
              className="enter font-display text-[40px] font-medium leading-[1.15] text-ink text-balance md:text-[64px]"
              style={enter(1)}
            >
              每日热点，
              <br />
              敲成<span className="accent-word">可行</span>的报告。
            </h1>

            {/* 副标即三条铁律本身（取自设计包文案） */}
            <p
              className="enter mt-8 max-w-[32em] text-[17px] leading-[1.8] text-ink-2"
              style={enter(2)}
            >
              Flint 把热点线索沉淀成可行性判定与深度报告。知道什么就说什么，不知道就明说——
              每个数字都带出处，每个空缺都留着形状。
            </p>

            <div className="enter mt-10 flex flex-wrap items-center gap-3" style={enter(3)}>
              <Link
                href="/plaza"
                className="inline-flex items-center gap-2 bg-cta-bg px-6 py-3.5 text-[15px] font-medium text-cta-fg transition-opacity hover:opacity-90"
                style={{ borderRadius: "var(--radius-cta)" }}
              >
                开始使用
              </Link>
              <Link
                href="/deliverables/del-demo-fixture-report"
                className="inline-flex items-center gap-2 border border-rail px-6 py-3.5 text-[15px] font-medium text-ink transition-colors hover:bg-raised"
                style={{ borderRadius: "var(--radius-cta)" }}
              >
                看一份样例报告
              </Link>
            </div>

            <p
              className="enter mt-12 font-mono text-[12px] tracking-[0.04em] text-ink-3"
              style={enter(4)}
            >
              REPORT · 已证事实盖印冻结，随附出处链
            </p>
          </div>

          {/* 判定卡当主角：承认不知道，是这个产品最贵的表达 */}
          <div className="enter glow-halo relative" style={enter(2)}>
            <div className="glow-frame p-7">
              <div className="flex items-baseline justify-between gap-4">
                <span className="font-mono text-[11px] uppercase tracking-[0.16em] text-ink-3">
                  Gate① · verdict
                </span>
                <span className="font-mono text-[11px] text-ink-3">4 / 4 缺口</span>
              </div>

              <p className="mt-5 font-display text-[34px] font-medium leading-none text-ink">
                {VERDICT_SAMPLE.label}
              </p>
              <p className="mt-3 font-mono text-[13px] text-ink-2">{VERDICT_SAMPLE.verdict}</p>

              <p className="mt-5 text-[14px] leading-[1.75] text-ink-2">
                这不是失败，是一个诚实的空白。下面四条是它自己列出的、要补什么才能判。
              </p>

              <ul className="mt-5 space-y-2.5 border-t border-rule pt-5">
                {VERDICT_SAMPLE.gaps.map((g) => (
                  <li key={g.missing_what} className="flex gap-2.5">
                    <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-[1px] bg-ink-3" aria-hidden />
                    <span className="min-w-0 flex-1 text-[13px] leading-[1.6] text-ink-2">
                      {g.missing_what}
                      <span className="ml-2 font-mono text-[11px] text-ink-3">
                        action · {g.action}
                      </span>
                    </span>
                  </li>
                ))}
              </ul>

              {/* unknown 竞品：与 weak 不同形——虚线中空，明标「未知」 */}
              <div className="mt-5 border-t border-rule pt-5">
                <p className="mb-2.5 font-mono text-[11px] text-ink-3">competitors · 2</p>
                <div className="flex flex-wrap gap-2">
                  {VERDICT_SAMPLE.competitors.map((c) => (
                    <span
                      key={c.name}
                      className="inline-flex items-center gap-2 rounded-[4px] border border-dashed border-rail px-2.5 py-1 font-mono text-[11px] text-ink-2"
                    >
                      <span className="h-2 w-2 rounded-full border border-dashed border-ink-3" aria-hidden />
                      {c.name} · strength 未知
                    </span>
                  ))}
                </div>
              </div>

              <p className="mt-5 border-t border-rule pt-5 font-mono text-[11px] leading-[1.7] text-ink-3">
                key_citation_ids [] · rationale_fact_ids []
                <br />
                均为空数组（无可溯源引用），此处不补占位。
              </p>
            </div>

            <p className="mt-4 px-2 font-mono text-[11px] leading-[1.7] text-ink-3">
              样例 · 非实时。取自本机录制回放真跑的引擎产出
              <br />
              harness/gate1_live.py replay-qwen → snap-job-gate1-live-qwen-verdict
            </p>
          </div>
        </div>
      </section>

      {/* ============ 少量证据点 ============ */}
      <section className="border-t border-rule">
        <div className="mx-auto max-w-[1180px] px-6 py-16">
          <div className="grid gap-x-10 gap-y-8 sm:grid-cols-2 lg:grid-cols-4">
            {PROOF_POINTS.map((p, i) => (
              <div key={p.k} className="enter flex flex-col gap-2" style={enter(i)}>
                <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-ink-3">
                  {p.k}
                </span>
                <span className="text-[17px] font-medium leading-[1.4] text-ink">{p.v}</span>
                <span className="font-mono text-[11px] leading-[1.6] text-ink-3">{p.note}</span>
              </div>
            ))}
          </div>

          <div className="mt-14 flex flex-wrap items-center justify-between gap-4 border-t border-rule pt-8">
            <p className="max-w-[36em] text-[14px] leading-[1.75] text-ink-2">
              想看它每一步到底调了哪个端点、哪些还没建？我们把整条链路和现状标签摊开写在一页里。
            </p>
            <Link
              href="/how-it-works"
              className="inline-flex items-center gap-2 border border-rail px-5 py-3 text-[14px] font-medium text-ink transition-colors hover:bg-raised"
              style={{ borderRadius: "var(--radius-cta)" }}
            >
              看完整 13 步旅程
            </Link>
          </div>
        </div>
      </section>

      {/* ============ 页脚站点图 ============ */}
      <footer className="border-t border-rule bg-raised">
        <div className="mx-auto max-w-[1180px] px-6 py-14">
          <div className="grid gap-10 md:grid-cols-[1.6fr_1fr]">
            <div>
              <p className="font-display text-[20px] text-ink">Flint 燧石</p>
              <p className="mt-3 max-w-[24em] text-[13px] leading-[1.75] text-ink-2">
                每日热点线索，沉淀成可行性判定与深度报告。数据区安静、对齐、等宽；温度在四周，准确在中间。
              </p>
            </div>

            {SITEMAP.map((col) => (
              <div key={col.group}>
                <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-3">
                  {col.group}
                </p>
                <ul className="mt-4 space-y-2.5">
                  {col.links.map((l) => (
                    <li key={l.label}>
                      <Link
                        href={l.href}
                        className="text-[13px] text-ink-2 transition-colors hover:text-ink"
                      >
                        {l.label}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          <div className="mt-12 border-t border-rule pt-6">
            <p className="font-mono text-[11px] text-ink-3">© 2026 FLINT 燧石</p>
          </div>
        </div>
      </footer>
    </main>
  )
}
