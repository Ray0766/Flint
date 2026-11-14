// I18N-04-b：名称三元组的呈现（主行 native / 次要行机翻）。
//
// PRINCIPLES#B7：name_native 是唯一权威 —— 主行**逐字**渲染它，NEVER 归一化、
// NEVER 用译名替代。
// PRINCIPLES#B8：name_display 是机翻派生物 —— 只能是**次要行**，字号与层级低于原名，
// 且必须带机翻标记；NEVER 单独出现、NEVER 与原名平级。

import type { JSX } from "react";

import { t } from "../../lib/i18n/t";

export type TranslatedText = {
  text: string;
  translated: boolean;
  translator: string;
  source_field: string;
};

export type NativeNameProps = {
  /** 原文名。权威字段，逐字渲染。 */
  nameNative: string;
  /** 原文的语言标记（来源语言，非 SystemLanguage）。 */
  nameLang?: string;
  /** 机翻派生槽；无译文时为 null/undefined —— 那时只显主行（A7 降级形态）。 */
  display?: TranslatedText | null;
};

export function NativeName({ nameNative, nameLang, display }: NativeNameProps): JSX.Element {
  return (
    <span className="native-name" data-name-lang={nameLang}>
      <span className="native-name__primary" data-testid="native-primary" lang={nameLang}>
        {nameNative}
      </span>
      {display ? (
        <span
          className="native-name__secondary"
          data-testid="native-secondary"
          data-translated={String(display.translated)}
          data-translator={display.translator}
          data-source-field={display.source_field}
        >
          {display.text}
          <span className="native-name__mark" data-testid="native-mt-mark">
            {t("card.name.translated_mark")}
          </span>
        </span>
      ) : null}
    </span>
  );
}
