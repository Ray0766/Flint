// DESIGN-17 验收：模型选择 + 推理强度（列表读环境配置；代码零硬编码模型名）。
//
// acceptance：**列表读环境配置；扫描器零命中硬编码模型名**。
//
// 为什么模型名一个都不许写进代码：模型会换。写死在某个组件里的型号，换代那天
// 要靠人去全仓找——找漏一处，那一处就永远用着旧模型，而界面上看不出任何区别：
// 它照样出结果，只是比别处差一档，账单也不一样。
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { codeOnly } from "../../test-utils/source";
import { ModelPicker, readModelConfig } from "./ModelPicker";

const CODE = codeOnly(readFileSync(join(__dirname, "ModelPicker.tsx"), "utf8"));

const ENV = {
  NEXT_PUBLIC_DESIGN_MODELS: "model-a|快模型, model-b|强模型",
  NEXT_PUBLIC_DESIGN_EFFORTS: "low,medium,high",
  NEXT_PUBLIC_DESIGN_MODEL_DEFAULT: "model-b",
  NEXT_PUBLIC_DESIGN_EFFORT_DEFAULT: "medium",
};

describe("readModelConfig（列表来自环境配置）", () => {
  it("模型与档位都从环境变量读，顺序照配置", () => {
    const config = readModelConfig(ENV);

    expect(config.models.map((m) => m.id)).toEqual(["model-a", "model-b"]);
    expect(config.models[0].label).toBe("快模型");
    expect(config.efforts).toEqual(["low", "medium", "high"]);
  });

  it("没给标签就用 id 当标签：NEVER 显示成空白一行", () => {
    const config = readModelConfig({ NEXT_PUBLIC_DESIGN_MODELS: "model-c" });

    expect(config.models).toEqual([{ id: "model-c", label: "model-c" }]);
  });

  it("默认值也来自配置：组件不替配置挑一个", () => {
    const config = readModelConfig(ENV);

    expect(config.defaultModelId).toBe("model-b");
    expect(config.defaultEffort).toBe("medium");
  });

  it("配置缺失时是空的，不是某个「常用型号」", () => {
    const config = readModelConfig({});

    expect(config.models).toEqual([]);
    expect(config.efforts).toEqual([]);
    expect(config.defaultModelId).toBeNull();
    expect(config.defaultEffort).toBeNull();
  });
});

describe("ModelPicker（渲染与透传）", () => {
  it("选项来自配置，一个不多一个不少", () => {
    render(
      <ModelPicker
        config={readModelConfig(ENV)}
        modelId="model-a"
        effort="low"
        onChange={vi.fn()}
      />,
    );

    expect(screen.getAllByTestId("model-picker-option").map((n) => n.textContent))
      .toEqual(["快模型", "强模型"]);
    expect(screen.getAllByTestId("model-picker-effort-option").map((n) => n.textContent))
      .toEqual(["low", "medium", "high"]);
  });

  it("换模型时把选择原样透传（不改档位）", () => {
    const onChange = vi.fn();
    render(
      <ModelPicker
        config={readModelConfig(ENV)}
        modelId="model-a"
        effort="low"
        onChange={onChange}
      />,
    );

    fireEvent.change(screen.getByTestId("model-picker-model"), {
      target: { value: "model-b" },
    });

    expect(onChange).toHaveBeenCalledWith({ modelId: "model-b", effort: "low" });
  });

  it("换档位时不改模型：两个维度互不牵连", () => {
    const onChange = vi.fn();
    render(
      <ModelPicker
        config={readModelConfig(ENV)}
        modelId="model-a"
        effort="low"
        onChange={onChange}
      />,
    );

    fireEvent.change(screen.getByTestId("model-picker-effort"), {
      target: { value: "high" },
    });

    expect(onChange).toHaveBeenCalledWith({ modelId: "model-a", effort: "high" });
  });

  it("没有可选模型时明说未配置，NEVER 回落到某个型号", () => {
    render(
      <ModelPicker
        config={readModelConfig({})}
        modelId={null}
        effort={null}
        onChange={vi.fn()}
      />,
    );

    const note = screen.getByTestId("model-picker-unconfigured");
    expect(note.textContent).toBeTruthy();
    expect(note.textContent).not.toBe("design.model.unconfigured");
    expect(screen.queryByTestId("model-picker")).toBeNull();
  });

  it("档位只做透传：组件不解释档位含义（那归后端）", () => {
    // 前端替档位写一套解释，就会与后端的说法有两套
    expect(CODE).not.toMatch(/effort\s*===\s*["']/);
  });

  it("源码里零模型名：连一个示例型号都不留", () => {
    expect(CODE).not.toMatch(
      /["'`](?:claude|gpt|gemini|llama|mistral|qwen|deepseek)-[a-z0-9]/i,
    );
  });

  it("文案 key 化：源码代码行零 CJK", () => {
    expect(CODE).not.toMatch(/[一-鿿]/);
  });
});
