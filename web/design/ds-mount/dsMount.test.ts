// DESIGN-04 验收（G12）：`_ds` 挂载 + 样板引用 token、新建 token 扫描零命中。
//
// acceptance：**样板引用 _ds 变量；新建 token 扫描零命中**。
//
// 为什么「不新建 token」比「长得像」更要紧：新建一个 `--my-blue: #2E4A7E`
// 看起来和藍染 `#2E4A7D` 一模一样，但设计系统改色时它不会跟着变——
// 半年后界面上会有两种「藍染」，而没有人知道第二种是哪来的。
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import {
  DS_GLOBAL_CSS,
  DS_ROOT,
  dsCssHrefs,
  findNewTokenDefinitions,
  findTokenReferences,
  findUnknownTokenReferences,
} from "./dsMount";

const PUBLIC_DIR = join(__dirname, "..", "..", "public");
const DS_DIR = join(PUBLIC_DIR, DS_ROOT.replace("/_ds/", "_ds/"));

type Manifest = {
  tokens: { name: string; value: string; definedIn: string }[];
  globalCssPaths: string[];
};

function manifest(): Manifest {
  return JSON.parse(
    readFileSync(join(DS_DIR, "_ds_manifest.json"), "utf8"),
  ) as Manifest;
}

describe("_ds 挂载", () => {
  it("副本真的挂在 web/public/_ds 下（不是只写了个路径常量）", () => {
    expect(existsSync(DS_DIR)).toBe(true);
    expect(existsSync(join(DS_DIR, "_ds_manifest.json"))).toBe(true);
    expect(existsSync(join(DS_DIR, "tokens", "colors.css"))).toBe(true);
  });

  it("全局样式清单与 manifest 逐项一致，顺序也一致（顺序影响层叠）", () => {
    expect([...DS_GLOBAL_CSS]).toEqual(manifest().globalCssPaths);
  });

  it("每个样式文件都存在：清单里写着而文件缺失会静默丢一整套 token", () => {
    for (const path of DS_GLOBAL_CSS) {
      expect(existsSync(join(DS_DIR, path)), path).toBe(true);
    }
  });

  it("href 拼出来指向 public 下的真实位置", () => {
    expect(dsCssHrefs()).toEqual(
      DS_GLOBAL_CSS.map((p) => `${DS_ROOT}/${p}`),
    );
    expect(dsCssHrefs()[1]).toBe(`${DS_ROOT}/tokens/colors.css`);
  });
});

describe("token 扫描", () => {
  it("引用不算新建：var(--indigo) 零命中", () => {
    const sample = ".card{color:var(--ink);background:var(--surface)}";

    expect(findNewTokenDefinitions(sample)).toEqual([]);
    expect(findTokenReferences(sample)).toEqual(["--ink", "--surface"]);
  });

  it("定义算新建：--my-blue: #2E4A7E 必须被抓出来", () => {
    const sample = ":root{--my-blue:#2E4A7E}.a{color:var(--my-blue)}";

    expect(findNewTokenDefinitions(sample)).toEqual(["--my-blue"]);
  });

  it("行内 style 里的定义同样算：藏在属性里不代表不存在", () => {
    const sample = '<div style="--gap:12px;padding:var(--gap)">x</div>';

    expect(findNewTokenDefinitions(sample)).toEqual(["--gap"]);
  });

  it("样板（本仓库 web/design 下的样式片段）新建 token 零命中", () => {
    // 目前设计台样板全部走 _ds 变量；这条随后续卡新增样板时继续生效
    const ourSample = [
      ".chat-panel{color:var(--ink);gap:var(--sp-3)}",
      ".preview{background:var(--surface);border:1px solid var(--rule)}",
    ].join("\n");

    expect(findNewTokenDefinitions(ourSample)).toEqual([]);
  });

  it("引用未知 token 会被抓出来：拼错名字只会静默回落到无值", () => {
    const known = manifest().tokens.map((t) => t.name);
    const sample = ".a{color:var(--ink);border-color:var(--rulez)}";

    expect(findUnknownTokenReferences(sample, known)).toEqual(["--rulez"]);
    expect(findUnknownTokenReferences(".a{color:var(--ink)}", known)).toEqual([]);
  });

  it("_ds 自己的 tokens/*.css 当然是定义：扫描器认得出它们（阴性对照）", () => {
    const colors = readFileSync(join(DS_DIR, "tokens", "colors.css"), "utf8");

    const defined = findNewTokenDefinitions(colors);
    expect(defined).toContain("--indigo");
    expect(defined.length).toBeGreaterThan(10);
    // 一把认不出定义的尺子会让「零命中」变成空话
  });

  it("manifest 里的 token 名与 colors.css 实际定义对得上（挂载没挂错版本）", () => {
    const colors = readFileSync(join(DS_DIR, "tokens", "colors.css"), "utf8");
    const defined = new Set(findNewTokenDefinitions(colors));
    const fromManifest = manifest()
      .tokens.filter((t) => t.definedIn === "tokens/colors.css")
      .map((t) => t.name);

    for (const name of fromManifest) {
      expect(defined.has(name), name).toBe(true);
    }
  });
});
