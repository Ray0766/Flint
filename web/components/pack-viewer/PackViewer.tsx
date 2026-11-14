import type { JSX } from "react";

import { NotProvided } from "../shell/NotProvided";
import { t } from "../../lib/i18n/t";

/**
 * UI-10 / 蓝本 P12：vibe_pack 查看器。
 *
 * ## 它与报告**必须长得明显不同**（技术约束清单第 31 条）
 *
 * 「它是给 AI 执行的包，排版上是否与给人读的报告明显不同？」
 *
 * 报告是给人读的散文；vibe_pack 是**喂给执行者的材料**。两者长得一样的话，
 * 用户会把包当报告读（读不下去），或把报告当包喂（喂进去的是散文）。
 *
 * 所以这里的形态是**清单**不是文章：九章逐条列出、任务表逐行列出、
 * 冻结件逐个带 sha256。正文一律 `<pre>`（等宽、不折行重排）——
 * 这些字是要被逐字复制走的，排版上的每一次「美化」都会改到它。
 *
 * ## Human Digest 带着「不进 AI 上下文」的标记
 *
 * BE-02 的响应里 `human_digest.for_ai_context === false`
 * （`pack_assemble` 的原话：「NEVER 并入 markdown」）。它是**监工视图**，
 * 与九章不是一回事。前端把这条标记**显示出来**——
 * 不显示的话，用户会把它和九章一起复制走。
 *
 * ## 「尚未生成」不是 404，也不是空包
 *
 * BE-02：`bundle is None` → `status: "not_generated"`，**不是 404**。
 * 前端照办：说「还没生成」，NEVER 显示一个空的九章骨架冒充生成过。
 */

export type PackChapter = { id: string; title: string; body: string };

export type PackView = {
  status: "generated" | "not_generated";
  chapters: PackChapter[];
  humanDigest: { body: string; forAiContext: boolean } | null;
  tasks: { id: string; title: string }[];
  contracts: { name: string; sha256: string }[];
};

export function PackViewer({ pack }: { pack: PackView | null }): JSX.Element {
  if (pack === null) {
    return (
      <section className="pack" data-pack-state="not_provided">
        <NotProvided label={t("pack.not_provided")} />
      </section>
    );
  }

  if (pack.status === "not_generated") {
    // 还没生成 ≠ 生成了一个空包。NEVER 画九章骨架冒充生成过。
    return (
      <section className="pack" data-pack-state="not_generated">
        <p className="pack__message">{t("pack.not_generated")}</p>
      </section>
    );
  }

  return (
    <section className="pack" data-pack-state="generated" data-pack-layout="checklist">
      <p className="pack__audience">{t("pack.audience")}</p>

      <ol className="pack__chapters">
        {pack.chapters.map((chapter) => (
          <li key={chapter.id} className="pack__chapter">
            <h3 className="pack__chapter-title">{chapter.id} · {chapter.title}</h3>
            {/* 逐字复制走的东西走 <pre>：任何重排都会改到它 */}
            <pre className="pack__chapter-body">{chapter.body}</pre>
          </li>
        ))}
      </ol>

      {pack.humanDigest !== null ? (
        <aside className="pack__digest" data-for-ai-context={
          String(pack.humanDigest.forAiContext)
        }>
          <p className="pack__digest-note">{t("pack.digest.not_for_ai")}</p>
          <pre className="pack__digest-body">{pack.humanDigest.body}</pre>
        </aside>
      ) : null}

      <table className="pack__tasks">
        <caption>{t("pack.tasks", { n: String(pack.tasks.length) })}</caption>
        <tbody>
          {pack.tasks.map((task) => (
            <tr key={task.id}>
              <td className="pack__task-id">{task.id}</td>
              <td>{task.title}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <ul className="pack__contracts">
        {pack.contracts.map((file) => (
          <li key={file.name} className="pack__contract">
            <span className="pack__contract-name">{file.name}</span>
            {/* 指纹逐字带上：包里那份与仓里那份对不对得上，靠的就是它 */}
            <span className="pack__contract-sha">{file.sha256}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
