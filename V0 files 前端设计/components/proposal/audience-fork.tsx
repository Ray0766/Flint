// P11 受众分叉（client）· 表单侧照 flint/compose/audience.py#plan_proposal 的真规则
//
// 清单 E 组：
// 29 受众 MUST 强制单选、**无默认**，NEVER 替用户预选；
//    选 ai_executor MUST **锁定** template_id=vibe_pack（不给第二个选项）。
// 30 受众混用的 422 MUST 如实报错，NEVER 吞掉。
//
// ⚠️ 提交端点（POST /projects/{id}/proposal，flint/api/compose.py）**本轮刻意未挂**
//    （owner 裁决：接上会把本轮验收从「屏做对了没有」混成「本地 qwen 写得好不好」）。
//    故提交按钮**不发请求**、**不造 job**，只如实说明「端点未接线」——
//    NEVER 做成看起来能点、点了没反应，也 NEVER 造一个永远 queued 的假 job。
//    表单侧的校验与呈现照做，接线当天把 submit 换成真请求即可。
"use client";

import { useState } from "react";
import { Bot, CircleAlert, User } from "lucide-react";

// 逐字照 flint/compose/audience.py#HUMAN_TEMPLATES（五套），NEVER 自造第六套
const HUMAN_TEMPLATES = ["generic", "thesis", "startup", "engineering", "grant"] as const;
type HumanTemplate = (typeof HUMAN_TEMPLATES)[number];
type Audience = "human_reader" | "ai_executor";

const TEMPLATE_LABEL: Record<HumanTemplate, string> = {
  generic: "generic · 通用",
  thesis: "thesis · 学位论文",
  startup: "startup · 创业计划",
  engineering: "engineering · 工程方案",
  grant: "grant · 科研资助",
};

export function AudienceFork({ projectId }: { projectId: string }) {
  // **无默认**：null 表示用户还没选。NEVER 预置任何一支。
  const [audience, setAudience] = useState<Audience | null>(null);
  const [template, setTemplate] = useState<HumanTemplate | null>(null);
  const [attempted, setAttempted] = useState(false);

  // 照 plan_proposal 的真规则做本地预检（**不是**代替后端判定，只是提前告诉用户）
  const localError =
    audience === null
      ? "audience 必选，且无默认——请先选一个受众。"
      : audience === "human_reader" && template === null
        ? "human_reader 必须选一套模板（五选一）。"
        : null;

  return (
    <div className="flex flex-col gap-6">
      {/* ① 受众：强制单选、无默认 */}
      <section
        className="border border-rule bg-surface p-5"
        style={{ borderRadius: "var(--radius-card)" }}
      >
        <h2 className="text-[14px] font-medium text-ink">① 受众 audience · 单选，无默认</h2>
        <p className="mt-1 text-[12px] leading-[1.7] text-ink-3">
          这一步没有推荐项、没有预选。两种受众产出的是两种东西，界面不替你选。
        </p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {(
            [
              {
                v: "human_reader" as const,
                Icon: User,
                title: "human_reader · 给人看",
                desc: "五套人类模板择一，产出 proposal（给人读的计划书）。",
              },
              {
                v: "ai_executor" as const,
                Icon: Bot,
                title: "ai_executor · 给 AI 执行",
                desc: "锁定 vibe_pack，产出 AI 执行包（不是给人读的排版）。",
              },
            ] as const
          ).map(({ v, Icon, title, desc }) => {
            const on = audience === v;
            return (
              <label
                key={v}
                className={`flex cursor-pointer items-start gap-3 border p-4 transition-colors ${
                  on ? "border-ink bg-raised" : "border-rule hover:border-rail"
                }`}
                style={{ borderRadius: "var(--radius)" }}
              >
                <input
                  type="radio"
                  name="audience"
                  checked={on}
                  onChange={() => {
                    setAudience(v);
                    // 选 ai_executor → 锁 vibe_pack，人类模板选择作废
                    if (v === "ai_executor") setTemplate(null);
                  }}
                  className="mt-1"
                />
                <span className="min-w-0">
                  <span className="flex items-center gap-2 text-[14px] font-medium text-ink">
                    <Icon className="h-4 w-4" strokeWidth={1.5} aria-hidden />
                    {title}
                  </span>
                  <span className="mt-1 block text-[12px] leading-[1.7] text-ink-2">{desc}</span>
                </span>
              </label>
            );
          })}
        </div>
      </section>

      {/* ② 模板：human_reader 五选一；ai_executor 锁定不可选 */}
      <section
        className="border border-rule bg-surface p-5"
        style={{ borderRadius: "var(--radius-card)" }}
      >
        <h2 className="text-[14px] font-medium text-ink">② 模板 template_id</h2>
        {audience === null ? (
          <p className="mt-2 font-mono text-[12px] text-ink-3">
            先选受众。模板选项取决于受众——此处不预先展示任何默认模板。
          </p>
        ) : audience === "ai_executor" ? (
          // 锁定：**不给第二个选项**，且写明这是契约锁定而非界面偏好
          <div className="mt-3">
            <span
              className="inline-flex items-center gap-2 border border-ink bg-ink px-3 py-1.5 font-mono text-[12px] text-primary-foreground"
              style={{ borderRadius: "var(--radius)" }}
            >
              template_id · vibe_pack（已锁定）
            </span>
            <p className="mt-3 max-w-[42em] text-[12px] leading-[1.7] text-ink-2">
              选 <span className="font-mono">ai_executor</span> 即锁定{" "}
              <span className="font-mono">vibe_pack</span>——这是契约规则
              （<span className="font-mono">plan_proposal</span>：ai_executor 传任何别的 template_id 都会被拒），
              不是界面替你做的偏好选择。
            </p>
          </div>
        ) : (
          <>
            <p className="mt-1 text-[12px] text-ink-3">五套人类模板择一（无默认）。</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {HUMAN_TEMPLATES.map((t) => {
                const on = template === t;
                return (
                  <button
                    key={t}
                    type="button"
                    onClick={() => setTemplate(t)}
                    aria-pressed={on}
                    className={`border px-3 py-1.5 font-mono text-[12px] transition-colors ${
                      on ? "border-ink bg-ink text-primary-foreground" : "border-rule text-ink-2 hover:border-rail"
                    }`}
                    style={{ borderRadius: "var(--radius)" }}
                  >
                    {TEMPLATE_LABEL[t]}
                  </button>
                );
              })}
            </div>
          </>
        )}
      </section>

      {/* 混用规则说明（清单 30）：把后端会 422 的两种情形先写明白 */}
      <section
        className="border border-dashed border-rail bg-raised p-5"
        style={{ borderRadius: "var(--radius-card)" }}
      >
        <p className="flex items-center gap-2 font-mono text-[11px] text-ink-2">
          <CircleAlert className="h-3.5 w-3.5" strokeWidth={1.5} aria-hidden />
          受众混用 → 后端 422（如实报错，NEVER 吞掉）
        </p>
        <ul className="mt-3 space-y-1.5 text-[12px] leading-[1.7] text-ink-2">
          <li>· 缺 audience → 422（契约：必选且无默认）</li>
          <li>· ai_executor + 非 vibe_pack 的 template_id → 422（锁定被违反）</li>
          <li>· human_reader 未给 template_id → 422（五选一必须选）</li>
          <li>· human_reader + 五套之外的 template_id → 422</li>
        </ul>
        <p className="mt-3 font-mono text-[10px] leading-[1.6] text-ink-3">
          界面的本地预检只是提前提示；判定以后端为准，422 到达时原样抬起 code 与 message。
        </p>
      </section>

      {/* 提交：端点未接线，如实说明。NEVER 假点击、NEVER 造假 job */}
      <section
        className="border border-dashed border-rail bg-raised p-5"
        style={{ borderRadius: "var(--radius-card)" }}
      >
        <p className="font-mono text-[12px] text-ink-2">
          POST /projects/{projectId}/proposal · <span className="text-ink">端点未接线</span>
        </p>
        <p className="mt-2 max-w-[42em] text-[13px] leading-[1.7] text-ink-2">
          该提交端点（<span className="font-mono">flint/api/compose.py</span>）本轮刻意未挂。
          原因不是没有 worker（<span className="font-mono">run_compose</span> 存在），
          而是接上会把本轮验收从「屏做对了没有」混成「本地模型写得好不好」，两件事要分开验。
        </p>
        <p className="mt-2 max-w-[42em] text-[13px] leading-[1.7] text-ink-2">
          所以这里<strong className="font-medium text-ink">没有可点的提交按钮</strong>——
          界面不做一个点了没反应的按钮，也不造一个永远 queued 的假作业。
          接线当天，把下面这份已校验的载荷直接发出去即可。
        </p>

        <button
          type="button"
          onClick={() => setAttempted(true)}
          className="mt-4 inline-flex border border-rule px-4 py-2 font-mono text-[12px] text-ink-2 hover:border-rail"
          style={{ borderRadius: "var(--radius)" }}
        >
          校验并生成载荷（本地，不发请求）
        </button>

        {attempted ? (
          localError !== null ? (
            <p className="mt-4 font-mono text-[12px] text-ink-2">{localError}</p>
          ) : (
            <pre
              className="mt-4 overflow-x-auto border border-rule bg-surface px-4 py-3 font-mono text-[11px] leading-[1.7] text-ink-2"
              style={{ borderRadius: "var(--radius)" }}
            >
{JSON.stringify(
  {
    audience,
    template_id: audience === "ai_executor" ? "vibe_pack" : template,
  },
  null,
  2,
)}
            </pre>
          )
        ) : null}
      </section>
    </div>
  );
}
