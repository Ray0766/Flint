import type { JSX } from "react";

import { COMBO_MAX, COMBO_MIN, comboCountValid } from "../../lib/topicClient";
import { t } from "../../lib/i18n/t";

/**
 * `WB-03-a`：中栏底部的输入区（蓝本第 137~152 行）。
 *
 * 蓝本形状照做：`flex-shrink:0` 的一块，两行 `resize:none` 的 textarea，
 * 下面一行控件，最右边是提交键。
 *
 * ## 两处刻意没照蓝本（都不是省事，是不能照）
 *
 * **一 · 模型下拉**（蓝本第 143~145 行：`Claude Haiku / Claude Sonnet / Qwen 本地`）。
 * NEVER 做：本仓这一批的规则第一条就是「生成一律走免费本地档，
 * NEVER 读任何 API key」——付费接口开通是 owner 人审节点（`S2-10`）。
 * 屏上摆一个选得中付费模型的下拉，等于把那道人审节点交给用户点。
 *
 * **二 · 模板下拉与思考档位**（第 140~148 行）。不是不做，是**不在这一卡**：
 * 五套模板的章节表是 `WB-05`，切换是 `WB-06`。在这里先摆一个能选、
 * 选了却不改变任何东西的下拉，比没有更坏。
 *
 * ## 提交键只表达「还不能提交」，NEVER 自己解释为什么被拒
 *
 * `chainClient` 那份既有口径（`docs/blocked/EMPTY-HYPOTHESIS-TWO-CODES.md`）：
 * 两条端点对空假设的答复不是同一句，前端存一句就要挑一句，挑哪句都会与另一条对不上。
 * 所以这里只做物理约束——**选卡数**与**假设非空**，
 * 而选卡数的上下限走既有的 `comboCountValid`，NEVER 在这一屏另写一个 2~5。
 */

export type WorkbenchComposerProps = {
  value: string;
  onChange: (next: string) => void;
  onSubmit: () => void;
  /** 这次要送出去的证据卡张数（由已选热点带出来的那些）。 */
  cardCount: number;
  /** 正在等答复：提交键按住不放第二次（重复提交会建出第二个项目）。 */
  busy: boolean;
};

export function WorkbenchComposer({
  value,
  onChange,
  onSubmit,
  cardCount,
  busy,
}: WorkbenchComposerProps): JSX.Element {
  const countOk = comboCountValid(cardCount);
  const canSubmit = countOk && value.trim() !== "" && !busy;

  return (
    <div className="wb-composer" data-wb-composer="true">
      <textarea
        className="wb-composer__input"
        data-wb-input="true"
        rows={2}
        value={value}
        placeholder={t("wb.composer.placeholder")}
        aria-label={t("wb.composer.label")}
        onChange={(event) => onChange(event.target.value)}
      />
      <div className="wb-composer__row">
        {/* 数量不够/超了时如实说是几张、要几张——**只说不够，不说为什么被拒**。
            按钮禁着而屏上一个字不说的话，用户只会反复点它。 */}
        {countOk ? null : (
          <span className="wb-composer__hint" data-wb-submit-hint="count">
            {t("wb.composer.count", { n: cardCount, min: COMBO_MIN, max: COMBO_MAX })}
          </span>
        )}
        <span className="wb-composer__spacer" />
        <button
          type="button"
          className="wb-composer__send"
          data-wb-submit="true"
          disabled={!canSubmit}
          onClick={onSubmit}
        >
          {busy ? t("wb.composer.sending") : t("wb.composer.send")}
        </button>
      </div>
    </div>
  );
}
