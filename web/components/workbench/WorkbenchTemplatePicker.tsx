"use client";

import type { JSX } from "react";

import { TEMPLATE_IDS } from "../../lib/sectionTables.generated";
import { t } from "../../lib/i18n/t";

/**
 * `WB-06`：五套模板的切换（蓝本第 140~142 行那个下拉）。
 *
 * 五个选项**来自那份生成物**（`TEMPLATE_IDS`，由 `assets/templates/*.yaml` 生成），
 * NEVER 在这里列一遍：列一遍的话，某天多一套模板时下拉里不会有它，
 * 而屏上看起来一切正常。
 *
 * 切换后章节导航与预览同步换——两者读的是同一处 `templateId` 状态
 * （`WB-05` 那张表按它取行）。
 *
 * 蓝本那个下拉旁边还有**模型**与**思考档位**两个选择器，本仓 NEVER 做：
 * 模型一律免费本地档（付费开通是 `S2-10` 的人审节点，摆一个能选中付费档的
 * 下拉等于把那道闸交给用户点）。
 */

export type WorkbenchTemplatePickerProps = {
  value: string;
  onChange: (templateId: string) => void;
};

export function WorkbenchTemplatePicker({
  value,
  onChange,
}: WorkbenchTemplatePickerProps): JSX.Element {
  return (
    <label className="wb-tpl" data-wb-template-picker={value}>
      <span className="wb-tpl__label">{t("wb.template.pick")}</span>
      <select
        className="wb-tpl__select"
        data-wb-template-select="true"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {TEMPLATE_IDS.map((id) => (
          <option key={id} value={id} data-wb-template-option={id}>
            {t(`wb.template.${id}`)}
          </option>
        ))}
      </select>
    </label>
  );
}
