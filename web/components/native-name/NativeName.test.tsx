// I18N-04-b 验收：主行 == native 字节等同；次要行带机翻标记。
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { NativeName, type TranslatedText } from "./NativeName";

const NATIVE = "全固体電池の量産ライン";           // 日文原文（含片假名与长音符）
const FULLWIDTH = "ＡＩ　半導体";                  // 全角字母 + 全角空格

const display: TranslatedText = {
  text: "All-solid-state battery production line",
  translated: true,
  translator: "identity@v1",
  source_field: "name_native",
};

describe("NativeName", () => {
  it("主行逐字渲染 native（字节等同，NEVER 归一化）", () => {
    render(<NativeName nameNative={NATIVE} nameLang="ja" display={display} />);
    const primary = screen.getByTestId("native-primary");
    expect(primary.textContent).toBe(NATIVE);
  });

  it("全角字符不被归一成半角", () => {
    render(<NativeName nameNative={FULLWIDTH} nameLang="ja" />);
    expect(screen.getByTestId("native-primary").textContent).toBe(FULLWIDTH);
  });

  it("次要行带机翻标记，且标注派生自哪个原文字段", () => {
    render(<NativeName nameNative={NATIVE} nameLang="ja" display={display} />);
    const secondary = screen.getByTestId("native-secondary");
    expect(secondary).toHaveAttribute("data-translated", "true");
    expect(secondary).toHaveAttribute("data-translator", "identity@v1");
    expect(secondary).toHaveAttribute("data-source-field", "name_native");
    expect(screen.getByTestId("native-mt-mark").textContent).toBeTruthy();
  });

  it("译文 NEVER 单独出现：没有 display 时只有主行", () => {
    render(<NativeName nameNative={NATIVE} nameLang="ja" />);
    expect(screen.getByTestId("native-primary").textContent).toBe(NATIVE);
    expect(screen.queryByTestId("native-secondary")).toBeNull();
  });

  it("A7 降级：display 为 null 时退回单行，NEVER 用原文冒充译文", () => {
    render(<NativeName nameNative={NATIVE} nameLang="ja" display={null} />);
    expect(screen.queryByTestId("native-secondary")).toBeNull();
    expect(screen.getAllByText(NATIVE)).toHaveLength(1);
  });

  it("主行在 DOM 顺序上先于次要行（次要行不得抢主位）", () => {
    render(<NativeName nameNative={NATIVE} nameLang="ja" display={display} />);
    const primary = screen.getByTestId("native-primary");
    const secondary = screen.getByTestId("native-secondary");
    expect(primary.compareDocumentPosition(secondary) & Node.DOCUMENT_POSITION_FOLLOWING)
      .toBeTruthy();
  });
});
