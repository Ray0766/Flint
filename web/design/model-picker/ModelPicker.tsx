// DESIGN-17：模型选择 + 推理强度（G23）。
//
// **代码里一个模型名都没有**。模型会换：写死在某个组件里的型号，换代那天要靠人
// 去全仓找——找漏一处，那一处就永远用着旧模型，而界面上看不出任何区别：
// 它照样出结果，只是比别处差一档，账单也不一样。
//
// 列表与默认值都从**环境配置**来，本组件只做三件事：读配置、让用户选、把选择透传。
// 连「默认选第一个」这种事也由配置说了算——组件替配置做决定，就等于又写死了一次。
//
// **配置缺失时不猜**：没有可选模型就说没有，而不是回落到某个「常用型号」。
// 回落的那一刻，用户以为自己在用他选的模型，实际上不是。
//
// 推理强度只做**透传**：档位含义归后端，前端替它解释就会有两套说法。

import type { JSX } from "react";

import { t } from "../../lib/i18n/t";

export type ModelOption = {
  id: string;
  label: string;
};

export type EffortOption = string;

export type DesignModelConfig = {
  models: ModelOption[];
  efforts: EffortOption[];
  defaultModelId: string | null;
  defaultEffort: EffortOption | null;
};

/** 从环境变量读配置。**这里是模型名唯一的来源**。 */
export function readModelConfig(env: Record<string, string | undefined>): DesignModelConfig {
  const models = (env.NEXT_PUBLIC_DESIGN_MODELS ?? "")
    .split(",")
    .map((entry) => entry.trim())
    .filter(Boolean)
    .map((entry) => {
      const [id, label] = entry.split("|");
      return { id: id.trim(), label: (label ?? id).trim() };
    });
  const efforts = (env.NEXT_PUBLIC_DESIGN_EFFORTS ?? "")
    .split(",")
    .map((e) => e.trim())
    .filter(Boolean);
  const defaultModelId = env.NEXT_PUBLIC_DESIGN_MODEL_DEFAULT?.trim() || null;
  const defaultEffort = env.NEXT_PUBLIC_DESIGN_EFFORT_DEFAULT?.trim() || null;
  return { models, efforts, defaultModelId, defaultEffort };
}

export type ModelPickerProps = {
  config: DesignModelConfig;
  modelId: string | null;
  effort: EffortOption | null;
  onChange: (next: { modelId: string | null; effort: EffortOption | null }) => void;
};

export function ModelPicker({
  config,
  modelId,
  effort,
  onChange,
}: ModelPickerProps): JSX.Element {
  if (config.models.length === 0) {
    // 没有可选模型就说没有：回落到某个「常用型号」会让用户以为自己在用他选的那个
    return <p data-testid="model-picker-unconfigured">{t("design.model.unconfigured")}</p>;
  }

  return (
    <div data-testid="model-picker" data-model-count={config.models.length}>
      <select
        data-testid="model-picker-model"
        value={modelId ?? ""}
        onChange={(e) => onChange({ modelId: e.target.value || null, effort })}
      >
        {config.models.map((model) => (
          <option key={model.id} value={model.id} data-testid="model-picker-option">
            {model.label}
          </option>
        ))}
      </select>
      <select
        data-testid="model-picker-effort"
        value={effort ?? ""}
        onChange={(e) => onChange({ modelId, effort: e.target.value || null })}
      >
        {config.efforts.map((level) => (
          <option key={level} value={level} data-testid="model-picker-effort-option">
            {level}
          </option>
        ))}
      </select>
    </div>
  );
}
