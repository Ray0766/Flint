// DESIGN-27 验收（隔离带·G2）：样板可辨识三件套。
//
// acceptance①「数字 XX.X% 与 [来源待补]/SRC-XXXX 语法强制；文件名 -mock 后缀」；
// acceptance②「水印节点缺失 → 渲染与导出拒绝（不可移除的可执行化）」。
//
// 为什么这三件套是**不可谈判**的（工单 §11-②）：探索期样板里的示例数字一旦被
// 截图外传当成真报告，燧石「每个数字有出处」这条立身之本就当场破产——
// 而外传的人往往不知道自己拿的是样板。三件套要保证：无论从哪个出口流出去，
// 它都自带「这是样板」这句话。
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { codeOnly } from "../../test-utils/source";
import {
  MOCK_WATERMARK_ATTR,
  MockIdentityViolation,
  checkMockPlaceholders,
  guardMock,
  hasWatermark,
  isMockFilename,
  usesPlaceholderSyntax,
} from "./mockIdentity";

const CODE = codeOnly(readFileSync(join(__dirname, "mockIdentity.ts"), "utf8"));

const CLEAN = `<div ${MOCK_WATERMARK_ATTR}="true"><p>渗透率 XX.X%（[来源待补]）</p></div>`;

describe("占位语法", () => {
  it("占位数字与占位来源都被认作合规", () => {
    expect(checkMockPlaceholders(CLEAN)).toEqual([]);
    expect(usesPlaceholderSyntax("渗透率 XX.X%")).toBe(true);
    expect(usesPlaceholderSyntax("来源 SRC-XXXX")).toBe(true);
    expect(usesPlaceholderSyntax("[来源待补]")).toBe(true);
  });

  it("具体数字被抓出来：42.7% 看起来就是真的，而 XX.X% 一眼假", () => {
    const violations = checkMockPlaceholders(
      `<div ${MOCK_WATERMARK_ATTR}="true">渗透率 42.7%</div>`,
    );

    expect(violations.map((v) => v.kind)).toContain("concrete_number");
    expect(violations.some((v) => v.detail.includes("42.7"))).toBe(true);
  });

  it("具体来源编号也被抓出来：SRC-1234 会被当成真出处", () => {
    const violations = checkMockPlaceholders("来源 SRC-1234");

    expect(violations.map((v) => v.kind)).toEqual(["concrete_source"]);
  });

  it("违规清单逐条列出，不是只报第一条", () => {
    const violations = checkMockPlaceholders("渗透率 42.7%，增速 18%，来源 SRC-1234");

    expect(violations.length).toBeGreaterThanOrEqual(3);
  });
});

describe("水印", () => {
  it("有水印节点即认", () => {
    expect(hasWatermark(CLEAN)).toBe(true);
  });

  it("没有水印就是没有：NEVER 补一个回去", () => {
    expect(hasWatermark("<div>无水印</div>")).toBe(false);
    // 「检测到缺失就补一个」等于告诉调用方「你怎么改都行，我兜着」，
    // 而这条规则的全部意义是它兜不住
    expect(CODE).not.toMatch(/inject|append.*watermark|watermark.*=\s*true/i);
  });
});

describe("文件名", () => {
  it.each([
    ["proposal-mock.html", true],
    ["proposal-mock.pdf", true],
    ["proposal.html", false],
    ["mock-proposal.html", false],
  ])("%s → %s", (name, expected) => {
    expect(isMockFilename(name)).toBe(expected);
  });
});

describe("guardMock（三件套缺一即拒）", () => {
  it("三件齐全时放行，且产物字节不变", () => {
    const out = guardMock(CLEAN, "proposal-mock.html");

    expect(out.html).toBe(CLEAN);
    expect(out.filename).toBe("proposal-mock.html");
  });

  it("缺水印 → 拒绝（渲染与导出共用这一道）", () => {
    expect(() => guardMock("<p>渗透率 XX.X%</p>", "proposal-mock.html")).toThrow(
      MockIdentityViolation,
    );
  });

  it("文件名没有 -mock → 拒绝", () => {
    expect(() => guardMock(CLEAN, "proposal.html")).toThrow(MockIdentityViolation);
  });

  it("正文里有真数字 → 拒绝", () => {
    expect(() =>
      guardMock(`<div ${MOCK_WATERMARK_ATTR}="true">42.7%</div>`, "a-mock.html"),
    ).toThrow(MockIdentityViolation);
  });

  it("拒绝时把**所有**违规列出来：一次说清才改得动", () => {
    try {
      guardMock("<p>渗透率 42.7%，来源 SRC-1234</p>", "proposal.html");
      throw new Error("NEVER 该走到这里");
    } catch (err) {
      const violations = (err as MockIdentityViolation).violations;
      const kinds = new Set(violations.map((v) => v.kind));
      expect(kinds.has("concrete_number")).toBe(true);
      expect(kinds.has("concrete_source")).toBe(true);
      expect(kinds.has("missing_watermark")).toBe(true);
      expect(kinds.has("filename")).toBe(true);
    }
  });

  it("拒绝时不返回半个产物：抛错而不是回一个「已修正」的版本", () => {
    let returned: unknown = "untouched";
    try {
      returned = guardMock("<p>42.7%</p>", "a.html");
    } catch {
      // 预期
    }
    expect(returned).toBe("untouched");
  });

  it("源码代码行零 CJK", () => {
    expect(CODE).not.toMatch(/[一-鿿]/);
  });
});
