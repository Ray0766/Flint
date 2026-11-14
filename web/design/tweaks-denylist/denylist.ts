// DESIGN-09：Tweaks 参数禁用词表（G13 后半）。
//
// Tweaks 面板调的是**外观**。一旦面板上出现「confidence threshold」「hide evidence」
// 「count」这样的旋钮，用户就能在一个看起来只管样式的地方**改掉内容本身**——
// 少显示几条证据、把把握度调高一档、把不想看的过滤掉。
//
// 而燧石的立身之本是「结论必有引用、数字必有出处」：一个能把证据调没的滑块，
// 等于给这条铁律开了一个**用户自己都不会意识到的后门**。所以这不是命名规范，
// 是内容与外观的边界。
//
// 拒绝发生在**提取**那一步：让它进了面板再灰掉，那颗旋钮已经在界面上了——
// 用户会问「为什么这个不能调」，而正确的回答是「它根本不该出现在这里」。
//
// 词边界按分隔符判：`--discount` 里的 count 不是 count 这个参数，`--counter` 也不是；
// 但 `--evidence-count` 是。一把见谁都拦的尺子会让人开始绕过它。

export class DeniedParameterError extends Error {}

/** 六词表（卡上 acceptance 逐字）。 */
export const DENIED_PARAM_WORDS: readonly string[] = [
  "evidence",
  "confidence",
  "threshold",
  "filter",
  "hide",
  "count",
];

export type TweakableParam = { name: string; value: string };

export type ExtractOptions = {
  /** 命中禁用词时：报错（默认）还是剔除 */
  onDenied?: "throw" | "skip";
  /** 剔除模式下把被剔的参数名交出去——静默剔除会让人以为源码里本来就没有它 */
  collectDenied?: (name: string) => void;
};

function words(name: string): string[] {
  return name.replace(/^--/, "").toLowerCase().split(/[-_]+/).filter(Boolean);
}

export function isDeniedParamName(name: string): boolean {
  const parts = words(name);
  return DENIED_PARAM_WORDS.some((word) => parts.includes(word));
}

const DEFINITION = /(--[a-z0-9_-]+)\s*:\s*([^;}]+)/gi;

/** 从源码里提取可调外观参数。命中禁用词的按 options 处理。 */
export function extractTweakableParams(
  source: string,
  options: ExtractOptions = {},
): TweakableParam[] {
  const mode = options.onDenied ?? "throw";
  const found: TweakableParam[] = [];

  for (const match of source.matchAll(DEFINITION)) {
    const name = match[1];
    const value = match[2].trim();
    if (isDeniedParamName(name)) {
      if (mode === "throw") {
        const hit = DENIED_PARAM_WORDS.filter((w) => words(name).includes(w));
        throw new DeniedParameterError(
          `${name} is not a presentation parameter (denied word: ${hit.join(", ")}): ` +
            "tweaks change how things look, never what is shown",
        );
      }
      options.collectDenied?.(name);
      continue;
    }
    found.push({ name, value });
  }
  return found;
}
