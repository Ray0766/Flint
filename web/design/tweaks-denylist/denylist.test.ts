// DESIGN-09 验收：Tweaks 参数禁用词表（六词拒绝提取）。
//
// acceptance：**evidence/confidence/threshold/filter/hide/count 参数名提取报错且不入面板**。
//
// 为什么是这六个词：Tweaks 面板调的是**外观**。一旦面板上出现
// 「confidence threshold」「hide evidence」「count」这样的旋钮，用户就能在一个
// 看起来只管样式的地方**改掉内容本身**——少显示几条证据、把把握度调高一档、
// 把不想看的过滤掉。而燧石的立身之本是「结论必有引用、数字必有出处」：
// 一个能把证据调没的滑块，等于给这条铁律开了一个用户自己都不会意识到的后门。
//
// 所以这不是命名规范，是**内容与外观的边界**。拒绝要发生在**提取**那一步：
// 让它进了面板再灰掉，那颗旋钮已经在界面上了。
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { codeOnly } from "../../test-utils/source";
import {
  DENIED_PARAM_WORDS,
  DeniedParameterError,
  extractTweakableParams,
  isDeniedParamName,
} from "./denylist";

const CODE = codeOnly(readFileSync(join(__dirname, "denylist.ts"), "utf8"));

const SOURCE = [
  ":root{",
  "  --gap: 12px;",
  "  --accent: var(--indigo);",
  "  --card-radius: 8px;",
  "}",
].join("\n");

describe("六词禁用表", () => {
  it("表就是卡上那六个词，一个不多一个不少", () => {
    expect([...DENIED_PARAM_WORDS].sort()).toEqual(
      ["confidence", "count", "evidence", "filter", "hide", "threshold"],
    );
  });

  it("六个词逐个命中（含大小写与连字符/下划线包裹）", () => {
    for (const word of DENIED_PARAM_WORDS) {
      expect(isDeniedParamName(`--${word}`), word).toBe(true);
      expect(isDeniedParamName(`--min-${word}`), word).toBe(true);
      expect(isDeniedParamName(`--${word}_level`), word).toBe(true);
      expect(isDeniedParamName(`--${word.toUpperCase()}`), word).toBe(true);
    }
  });

  it("正常外观参数不误伤：这把尺子不能见谁都拦", () => {
    for (const ok of [
      "--gap", "--accent", "--card-radius", "--font-size", "--shadow-overlay",
      "--column-width", "--discount",   // discount 含 count 但不是 count 这个词
    ]) {
      expect(isDeniedParamName(ok), ok).toBe(false);
    }
  });

  it("词边界按分隔符判：counter/evidences 这种整词不同的不算命中", () => {
    expect(isDeniedParamName("--counter")).toBe(false);
    expect(isDeniedParamName("--evidences")).toBe(false);
    // 但真正的复合参数名照样拦得住
    expect(isDeniedParamName("--evidence-count")).toBe(true);
  });
});

describe("提取时拒绝", () => {
  it("干净源码全部提取出来", () => {
    const params = extractTweakableParams(SOURCE);

    expect(params.map((p) => p.name)).toEqual(["--gap", "--accent", "--card-radius"]);
  });

  it("含禁用词的参数**在提取那一步**就报错，而不是先进面板再灰掉", () => {
    const dirty = SOURCE.replace("--gap: 12px;", "--confidence-threshold: 0.6;");

    expect(() => extractTweakableParams(dirty)).toThrow(DeniedParameterError);
  });

  it("报错说清是哪个参数、命中哪个词：一句「参数非法」查不出所以然", () => {
    const dirty = SOURCE.replace("--gap: 12px;", "--hide-evidence: 1;");

    try {
      extractTweakableParams(dirty);
      throw new Error("NEVER 该走到这里");
    } catch (err) {
      const message = (err as Error).message;
      expect(message).toContain("--hide-evidence");
      expect(message).toContain("hide");
    }
  });

  it("宽松模式下命中项被**剔除**而不是混进面板", () => {
    const dirty = SOURCE.replace("--gap: 12px;", "--evidence-count: 3;");

    const params = extractTweakableParams(dirty, { onDenied: "skip" });

    expect(params.map((p) => p.name)).toEqual(["--accent", "--card-radius"]);
    // 剔除也要留痕：调用方拿得到被剔的清单，NEVER 静默吞掉
    expect(extractTweakableParams(dirty, { onDenied: "skip" }).length).toBe(2);
  });

  it("被剔的清单交得出来：静默剔除会让人以为源码里本来就没有那个参数", () => {
    const dirty = SOURCE.replace("--gap: 12px;", "--evidence-count: 3;");
    const denied: string[] = [];

    extractTweakableParams(dirty, { onDenied: "skip", collectDenied: denied.push.bind(denied) });

    expect(denied).toEqual(["--evidence-count"]);
  });

  it("一条都不剩时返回空数组而不是抛错：空面板是明确状态", () => {
    const params = extractTweakableParams(":root{--evidence: 1;}", { onDenied: "skip" });

    expect(params).toEqual([]);
  });

  it("提取只认定义，不认引用（与 DESIGN-08 同一条口径）", () => {
    const params = extractTweakableParams(".a{padding:var(--gap)}");

    expect(params).toEqual([]);
  });

  it("源码代码行零 CJK", () => {
    expect(CODE).not.toMatch(/[一-鿿]/);
  });
});
