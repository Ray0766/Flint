/* @ds-bundle: {"format":4,"namespace":"FlintDesignSystem_8fd95b","components":[{"name":"Button","sourcePath":"components/core/Button.jsx"},{"name":"Dialog","sourcePath":"components/core/Dialog.jsx"},{"name":"Input","sourcePath":"components/core/Input.jsx"},{"name":"Tabs","sourcePath":"components/core/Tabs.jsx"},{"name":"ChannelValue","sourcePath":"components/data/ChannelValue.jsx"},{"name":"CitationMark","sourcePath":"components/data/CitationMark.jsx"},{"name":"DataTable","sourcePath":"components/data/DataTable.jsx"},{"name":"ChartPlaceholder","sourcePath":"components/status/ChartPlaceholder.jsx"},{"name":"DegradedNotice","sourcePath":"components/status/DegradedNotice.jsx"},{"name":"EmptyState","sourcePath":"components/status/EmptyState.jsx"},{"name":"SealedBlock","sourcePath":"components/status/SealedBlock.jsx"},{"name":"StatusMark","sourcePath":"components/status/StatusMark.jsx"},{"name":"VoidBlock","sourcePath":"components/status/VoidBlock.jsx"},{"name":"PaperSurface","sourcePath":"components/surfaces/PaperSurface.jsx"},{"name":"StickerTag","sourcePath":"components/surfaces/StickerTag.jsx"}],"sourceHashes":{"components/core/Button.jsx":"730265583d41","components/core/Dialog.jsx":"0651f9d01e84","components/core/Input.jsx":"753201e2eacb","components/core/Tabs.jsx":"2dabb504d611","components/data/ChannelValue.jsx":"7f604b7300a9","components/data/CitationMark.jsx":"45b791b4911c","components/data/DataTable.jsx":"7fca41d8fb4f","components/status/ChartPlaceholder.jsx":"85a7a2dc557b","components/status/DegradedNotice.jsx":"c3581a705dd2","components/status/EmptyState.jsx":"f303e28cd206","components/status/SealedBlock.jsx":"376473442315","components/status/StatusMark.jsx":"ab5841049797","components/status/VoidBlock.jsx":"0a4567432183","components/surfaces/PaperSurface.jsx":"3082dfa3eba2","components/surfaces/StickerTag.jsx":"434d4e6ae0af","ui_kits/app/leads.screen.jsx":"21c813f8c5f8","ui_kits/app/report.screen.jsx":"17661586d260","ui_kits/marketing/landing.screen.jsx":"73f0580ca9cc"},"inlinedExternals":[],"unexposedExports":[]} */

(() => {

const __ds_ns = (window.FlintDesignSystem_8fd95b = window.FlintDesignSystem_8fd95b || {});

const __ds_scope = {};

(__ds_ns.__errors = __ds_ns.__errors || []);

// components/core/Button.jsx
try { (() => {
function Button({
  variant = "primary",
  size = "md",
  disabled = false,
  type = "button",
  onClick,
  children,
  style
}) {
  const [hover, setHover] = React.useState(false);
  const [active, setActive] = React.useState(false);
  const v = {
    primary: {
      background: hover ? "#DFAD2B" : "var(--sulfur)",
      color: "var(--ink)",
      border: "1px solid var(--ink)",
      boxShadow: active ? "0 0 0 rgba(27,42,46,.18)" : "2px 2px 0 rgba(27,42,46,.18)"
    },
    secondary: {
      background: hover ? "var(--paper-2)" : "var(--surface)",
      color: "var(--ink)",
      border: hover ? "1px solid var(--ink)" : "1px solid var(--ink-2)",
      boxShadow: "none"
    },
    ghost: {
      background: "transparent",
      color: "var(--indigo)",
      border: "1px solid transparent",
      boxShadow: "none",
      textDecoration: "underline",
      textDecorationThickness: hover ? 2 : 1,
      textDecorationColor: hover ? "var(--sulfur)" : "currentColor",
      textUnderlineOffset: 3
    }
  }[variant];
  return /*#__PURE__*/React.createElement("button", {
    type: type,
    disabled: disabled,
    onClick: onClick,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => {
      setHover(false);
      setActive(false);
    },
    onMouseDown: () => setActive(true),
    onMouseUp: () => setActive(false),
    style: {
      fontFamily: "var(--font-body)",
      fontWeight: 600,
      fontSize: size === "sm" ? 13 : 14,
      lineHeight: 1.2,
      padding: size === "sm" ? "6px 14px" : "11px 20px",
      borderRadius: "var(--r-data)",
      display: "inline-flex",
      alignItems: "center",
      gap: 8,
      cursor: disabled ? "not-allowed" : "pointer",
      opacity: disabled ? 0.45 : 1,
      transform: active && variant === "primary" ? "translate(2px,2px)" : "none",
      transition: "background .15s,border-color .15s,box-shadow .1s,transform .05s",
      ...v,
      ...style
    }
  }, children);
}
Object.assign(__ds_scope, { Button });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Button.jsx", error: String((e && e.message) || e) }); }

// components/core/Dialog.jsx
try { (() => {
function Dialog({
  open,
  onClose,
  title,
  children,
  footer,
  width = 480
}) {
  React.useEffect(() => {
    if (!open) return;
    const h = e => {
      if (e.key === "Escape") onClose && onClose();
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [open, onClose]);
  if (!open) return null;
  return /*#__PURE__*/React.createElement("div", {
    onClick: onClose,
    style: {
      position: "fixed",
      inset: 0,
      background: "rgba(27,42,46,.42)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      zIndex: 100,
      padding: 24
    }
  }, /*#__PURE__*/React.createElement("div", {
    role: "dialog",
    "aria-modal": "true",
    onClick: e => e.stopPropagation(),
    style: {
      width,
      maxWidth: "100%",
      background: "var(--surface)",
      backgroundImage: "var(--tex-paper)",
      border: "1px solid var(--rule)",
      borderRadius: "var(--r-card)",
      boxShadow: "var(--shadow-overlay)",
      overflow: "hidden"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      padding: "16px 24px",
      borderBottom: "1px solid var(--rule)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: "var(--font-display)",
      fontSize: 20,
      lineHeight: 1.15,
      color: "var(--ink)"
    }
  }, title), /*#__PURE__*/React.createElement("button", {
    onClick: onClose,
    "aria-label": "\u5173\u95ED",
    style: {
      background: "none",
      border: "none",
      cursor: "pointer",
      fontFamily: "var(--font-mono)",
      fontSize: 14,
      color: "var(--ink-3)",
      padding: 4
    }
  }, "\u2715")), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 24,
      fontSize: 14,
      lineHeight: 1.6,
      color: "var(--ink)"
    }
  }, children), footer && /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      justifyContent: "flex-end",
      gap: 12,
      padding: "16px 24px",
      borderTop: "1px solid var(--rule)",
      background: "var(--paper-2)"
    }
  }, footer)));
}
Object.assign(__ds_scope, { Dialog });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Dialog.jsx", error: String((e && e.message) || e) }); }

// components/core/Input.jsx
try { (() => {
function Input({
  label,
  value,
  defaultValue,
  onChange,
  placeholder,
  mono = false,
  hint,
  error,
  disabled = false,
  type = "text",
  style
}) {
  const [focus, setFocus] = React.useState(false);
  const id = React.useId();
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 6,
      ...style
    }
  }, label && /*#__PURE__*/React.createElement("label", {
    htmlFor: id,
    style: {
      fontFamily: "var(--font-mono)",
      fontSize: 12,
      color: "var(--ink-2)",
      letterSpacing: "0.04em"
    }
  }, label), /*#__PURE__*/React.createElement("input", {
    id: id,
    type: type,
    value: value,
    defaultValue: defaultValue,
    placeholder: placeholder,
    disabled: disabled,
    onChange: onChange,
    onFocus: () => setFocus(true),
    onBlur: () => setFocus(false),
    style: {
      fontFamily: mono ? "var(--font-mono)" : "var(--font-body)",
      fontVariantNumeric: "tabular-nums",
      fontSize: 14,
      lineHeight: 1.5,
      padding: "9px 12px",
      color: "var(--ink)",
      background: disabled ? "var(--paper-2)" : "var(--surface)",
      border: `1px solid ${error ? "var(--ink-2)" : focus ? "var(--indigo)" : "var(--rule)"}`,
      borderRadius: "var(--r-data)",
      outline: focus ? "1px solid var(--indigo)" : "none",
      opacity: disabled ? 0.6 : 1,
      transition: "border-color .15s"
    }
  }), error ? /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      color: "var(--ink-2)",
      display: "flex",
      gap: 6,
      alignItems: "baseline"
    }
  }, /*#__PURE__*/React.createElement("span", {
    "aria-hidden": "true",
    style: {
      width: 9,
      height: 9,
      border: "1px solid var(--ink-2)",
      backgroundImage: "var(--tex-hatch)",
      boxSizing: "border-box",
      display: "inline-block",
      flex: "none",
      alignSelf: "center"
    }
  }), error) : hint ? /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      color: "var(--ink-3)"
    }
  }, hint) : null);
}
Object.assign(__ds_scope, { Input });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Input.jsx", error: String((e && e.message) || e) }); }

// components/core/Tabs.jsx
try { (() => {
function Tabs({
  items,
  active,
  onChange,
  style
}) {
  const [inner, setInner] = React.useState(items[0] && items[0].key);
  const cur = active !== undefined ? active : inner;
  const set = k => {
    if (active === undefined) setInner(k);
    onChange && onChange(k);
  };
  return /*#__PURE__*/React.createElement("div", {
    role: "tablist",
    style: {
      display: "flex",
      gap: 24,
      borderBottom: "1px solid var(--rule)",
      ...style
    }
  }, items.map(it => {
    const on = it.key === cur;
    return /*#__PURE__*/React.createElement("button", {
      key: it.key,
      role: "tab",
      "aria-selected": on,
      onClick: () => set(it.key),
      style: {
        background: "none",
        border: "none",
        cursor: "pointer",
        padding: "8px 2px 10px",
        fontFamily: "var(--font-body)",
        fontSize: 14,
        fontWeight: on ? 600 : 400,
        color: on ? "var(--ink)" : "var(--ink-2)",
        boxShadow: on ? "inset 0 -2px 0 var(--indigo)" : "none",
        display: "inline-flex",
        alignItems: "baseline",
        gap: 6
      }
    }, it.label, it.count !== undefined && /*#__PURE__*/React.createElement("span", {
      style: {
        fontFamily: "var(--font-mono)",
        fontVariantNumeric: "tabular-nums",
        fontSize: 12,
        color: on ? "var(--indigo)" : "var(--ink-3)"
      }
    }, it.count));
  }));
}
Object.assign(__ds_scope, { Tabs });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Tabs.jsx", error: String((e && e.message) || e) }); }

// components/data/ChannelValue.jsx
try { (() => {
/* 三通道记号：事实=实心方 / 价格=空心方 / 涉我=括线。靠形状区分，不靠颜色。 */
function ChannelValue({
  channel = "fact",
  value,
  unit,
  dim = false,
  style
}) {
  const color = dim ? "var(--ink-2)" : "var(--ink)";
  const markColor = dim ? "var(--ink-3)" : "var(--indigo)";
  const sq = {
    display: "inline-block",
    width: 7,
    height: 7,
    flex: "none"
  };
  const mark = channel === "fact" ? /*#__PURE__*/React.createElement("span", {
    "aria-label": "\u4E8B\u5B9E",
    style: {
      ...sq,
      background: markColor
    }
  }) : channel === "price" ? /*#__PURE__*/React.createElement("span", {
    "aria-label": "\u4EF7\u683C",
    style: {
      ...sq,
      border: `1.5px solid ${markColor}`,
      boxSizing: "border-box"
    }
  }) : null;
  const bracket = {
    display: "inline-block",
    width: 5,
    height: "0.95em",
    flex: "none",
    borderTop: `1.5px solid ${markColor}`,
    borderBottom: `1.5px solid ${markColor}`
  };
  return /*#__PURE__*/React.createElement("span", {
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: 6,
      fontFamily: "var(--font-mono)",
      fontVariantNumeric: "tabular-nums",
      fontSize: "1em",
      color,
      whiteSpace: "nowrap",
      ...style
    }
  }, mark, channel === "self" && /*#__PURE__*/React.createElement("span", {
    "aria-label": "\u6D89\u6211",
    style: {
      ...bracket,
      borderLeft: `1.5px solid ${markColor}`
    }
  }), /*#__PURE__*/React.createElement("span", null, value), channel === "self" && /*#__PURE__*/React.createElement("span", {
    "aria-hidden": "true",
    style: {
      ...bracket,
      borderRight: `1.5px solid ${markColor}`
    }
  }), unit && /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: "0.85em",
      color: "var(--ink-2)"
    }
  }, unit));
}
Object.assign(__ds_scope, { ChannelValue });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/data/ChannelValue.jsx", error: String((e && e.message) || e) }); }

// components/data/CitationMark.jsx
try { (() => {
/* 可点角标 + 溯源浮层。source 为空 = 如实展示「接口未提供出处」。 */
function CitationMark({
  index,
  source = null,
  style
}) {
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef(null);
  React.useEffect(() => {
    if (!open) return;
    const h = e => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, [open]);
  return /*#__PURE__*/React.createElement("span", {
    ref: ref,
    style: {
      position: "relative",
      display: "inline-block",
      ...style
    }
  }, /*#__PURE__*/React.createElement("button", {
    onClick: () => setOpen(!open),
    "aria-expanded": open,
    style: {
      background: open ? "var(--indigo-soft)" : "none",
      border: "none",
      cursor: "pointer",
      padding: "0 3px",
      fontFamily: "var(--font-mono)",
      fontVariantNumeric: "tabular-nums",
      fontSize: "0.75em",
      color: "var(--indigo)",
      verticalAlign: "super",
      lineHeight: 1,
      borderRadius: 2,
      textDecoration: "underline",
      textDecorationThickness: 1,
      textUnderlineOffset: 2
    }
  }, "[", index, "]"), open && /*#__PURE__*/React.createElement("span", {
    role: "tooltip",
    style: {
      position: "absolute",
      left: 0,
      top: "calc(100% + 6px)",
      zIndex: 50,
      width: 260,
      display: "block",
      background: "var(--surface)",
      backgroundImage: "var(--tex-note)",
      border: "1px solid var(--rule)",
      borderLeft: "3px solid var(--indigo)",
      borderRadius: "var(--r-data)",
      boxShadow: "var(--shadow-overlay)",
      padding: "12px 14px",
      fontFamily: "var(--font-body)",
      fontSize: 13,
      lineHeight: 1.6,
      color: "var(--ink)",
      textAlign: "left"
    }
  }, source ? /*#__PURE__*/React.createElement("span", {
    style: {
      display: "block"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      display: "block",
      fontWeight: 600
    }
  }, source.title), source.detail && /*#__PURE__*/React.createElement("span", {
    style: {
      display: "block",
      color: "var(--ink-2)",
      marginTop: 2
    }
  }, source.detail), /*#__PURE__*/React.createElement("span", {
    style: {
      display: "block",
      fontFamily: "var(--font-mono)",
      fontVariantNumeric: "tabular-nums",
      fontSize: 12,
      color: "var(--ink-3)",
      marginTop: 6
    }
  }, [source.id, source.date].filter(Boolean).join(" · ")), source.url && /*#__PURE__*/React.createElement("a", {
    href: source.url,
    style: {
      display: "inline-block",
      fontSize: 12,
      marginTop: 6
    }
  }, "\u67E5\u770B\u539F\u6587")) : /*#__PURE__*/React.createElement("span", {
    style: {
      display: "block",
      color: "var(--ink-2)"
    }
  }, /*#__PURE__*/React.createElement("span", {
    "aria-hidden": "true",
    style: {
      width: 9,
      height: 9,
      border: "1px solid var(--ink-2)",
      backgroundImage: "var(--tex-hatch)",
      boxSizing: "border-box",
      display: "inline-block",
      marginRight: 6
    }
  }), "\u63A5\u53E3\u672A\u63D0\u4F9B\u51FA\u5904", /*#__PURE__*/React.createElement("span", {
    style: {
      display: "block",
      fontSize: 12,
      color: "var(--ink-3)",
      marginTop: 4
    }
  }, "\u8BE5\u5B57\u6BB5\u7684\u6EAF\u6E90\u4FE1\u606F\u7F3A\u5931\uFF0C\u6309\u7F3A\u53E3\u5982\u5B9E\u5C55\u793A\u3002"))));
}
Object.assign(__ds_scope, { CitationMark });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/data/CitationMark.jsx", error: String((e && e.message) || e) }); }

// components/data/DataTable.jsx
try { (() => {
/* 表是真相：数字右对齐等宽对位，网格线克制，靠对齐成列。 */
function DataTable({
  columns,
  rows,
  caption,
  style
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      border: "1px solid var(--rule)",
      borderRadius: "var(--r-data)",
      background: "var(--surface)",
      overflow: "hidden",
      ...style
    }
  }, /*#__PURE__*/React.createElement("table", {
    style: {
      width: "100%",
      borderCollapse: "collapse",
      fontSize: 13,
      lineHeight: 1.5
    }
  }, caption && /*#__PURE__*/React.createElement("caption", {
    style: {
      captionSide: "top",
      textAlign: "left",
      padding: "10px 14px",
      fontFamily: "var(--font-mono)",
      fontSize: 12,
      letterSpacing: "0.04em",
      color: "var(--ink-3)",
      borderBottom: "1px solid var(--rule)"
    }
  }, caption), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, columns.map(c => /*#__PURE__*/React.createElement("th", {
    key: c.key,
    scope: "col",
    style: {
      textAlign: c.align || (c.channel || c.num ? "right" : "left"),
      padding: "8px 14px",
      fontFamily: "var(--font-mono)",
      fontWeight: 500,
      fontSize: 12,
      letterSpacing: "0.04em",
      color: "var(--ink-3)",
      borderBottom: "1px solid var(--rule)",
      whiteSpace: "nowrap"
    }
  }, c.label)))), /*#__PURE__*/React.createElement("tbody", null, rows.map((r, i) => /*#__PURE__*/React.createElement("tr", {
    key: i
  }, columns.map(c => {
    const v = r[c.key];
    return /*#__PURE__*/React.createElement("td", {
      key: c.key,
      style: {
        textAlign: c.align || (c.channel || c.num ? "right" : "left"),
        padding: "9px 14px",
        borderBottom: i < rows.length - 1 ? "1px solid var(--rule)" : "none",
        color: "var(--ink)",
        fontFamily: c.num && !c.channel ? "var(--font-mono)" : "inherit",
        fontVariantNumeric: "tabular-nums"
      }
    }, c.channel ? /*#__PURE__*/React.createElement(__ds_scope.ChannelValue, {
      channel: c.channel,
      value: v,
      unit: c.unit
    }) : v);
  }))))));
}
Object.assign(__ds_scope, { DataTable });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/data/DataTable.jsx", error: String((e && e.message) || e) }); }

// components/status/ChartPlaceholder.jsx
try { (() => {
/* 表是真相，图只是摘要：零数据点占位。不引图表库、不画数据点、不做聚合。 */
function ChartPlaceholder({
  title = "图表占位",
  sourceNote,
  height = 180,
  style
}) {
  return /*#__PURE__*/React.createElement("figure", {
    style: {
      margin: 0,
      border: "1px solid var(--rule)",
      borderRadius: "var(--r-data)",
      background: "var(--surface)",
      overflow: "hidden",
      ...style
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      position: "relative",
      height,
      background: "var(--paper-2)",
      backgroundImage: "var(--tex-press)",
      boxShadow: "var(--emboss)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center"
    }
  }, /*#__PURE__*/React.createElement("span", {
    "aria-hidden": "true",
    style: {
      position: "absolute",
      left: 16,
      top: 12,
      bottom: 26,
      width: 1,
      background: "var(--ink-3)",
      opacity: 0.5
    }
  }), /*#__PURE__*/React.createElement("span", {
    "aria-hidden": "true",
    style: {
      position: "absolute",
      left: 16,
      right: 16,
      bottom: 26,
      height: 1,
      background: "var(--ink-3)",
      opacity: 0.5
    }
  }), /*#__PURE__*/React.createElement("span", {
    "aria-hidden": "true",
    style: {
      position: "absolute",
      left: 16,
      right: 16,
      bottom: 26,
      top: 12,
      backgroundImage: "repeating-linear-gradient(180deg, rgba(27,42,46,.05) 0 1px, transparent 1px 28px)"
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: "var(--font-mono)",
      fontSize: 12,
      letterSpacing: "0.04em",
      color: "var(--ink-3)",
      background: "var(--paper-2)",
      padding: "2px 10px"
    }
  }, title, " \xB7 \u96F6\u6570\u636E\u70B9")), /*#__PURE__*/React.createElement("figcaption", {
    style: {
      padding: "10px 14px",
      fontSize: 12,
      lineHeight: 1.6,
      color: "var(--ink-2)",
      borderTop: "1px solid var(--rule)"
    }
  }, "\u8868\u662F\u771F\u76F8\uFF0C\u56FE\u53EA\u662F\u6458\u8981\u3002", sourceNote || "此处不渲染数据点；数值以下方表格及其出处链为准。"));
}
Object.assign(__ds_scope, { ChartPlaceholder });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/status/ChartPlaceholder.jsx", error: String((e && e.message) || e) }); }

// components/status/DegradedNotice.jsx
try { (() => {
/* 降级生成 = 复印件的网点。网点底纹 + 明文标注。 */
function DegradedNotice({
  children,
  style
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 12,
      alignItems: "flex-start",
      background: "var(--surface)",
      backgroundImage: "var(--tex-halftone)",
      border: "1px solid var(--rule)",
      borderRadius: "var(--r-data)",
      padding: "12px 16px",
      ...style
    }
  }, /*#__PURE__*/React.createElement("span", {
    "aria-hidden": "true",
    style: {
      flex: "none",
      marginTop: 5,
      width: 10,
      height: 10,
      background: "radial-gradient(var(--ink-3) 1.2px, transparent 1.5px) 0 0/5px 5px"
    }
  }), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: "var(--font-mono)",
      fontSize: 12,
      letterSpacing: "0.04em",
      color: "var(--ink-3)"
    }
  }, "\u964D\u7EA7\u751F\u6210"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 13,
      lineHeight: 1.6,
      color: "var(--ink-2)",
      marginTop: 2
    }
  }, children || "本段在部分数据源不可用时生成，完整性低于正常水平。")));
}
Object.assign(__ds_scope, { DegradedNotice });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/status/DegradedNotice.jsx", error: String((e && e.message) || e) }); }

// components/status/EmptyState.jsx
try { (() => {
/* 空态插画：单线手绘 + 单色平涂，indigo/sulfur/moss。题材取自产品世界。 */
function Art({
  kind
}) {
  const stroke = "var(--indigo)";
  if (kind === "spark") return /*#__PURE__*/React.createElement("svg", {
    width: "88",
    height: "72",
    viewBox: "0 0 88 72",
    fill: "none",
    "aria-hidden": "true"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M22 52 L40 40 L34 30 L52 20",
    stroke: stroke,
    strokeWidth: "1.5",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M30 56 C24 60 18 60 14 56 C18 54 22 50 24 46 Z",
    fill: "var(--moss)",
    opacity: ".85"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M56 18 l5 -8 M60 24 l9 -3 M58 32 l7 4 M50 12 l-1 -9",
    stroke: "var(--sulfur)",
    strokeWidth: "2",
    strokeLinecap: "round"
  }), /*#__PURE__*/React.createElement("circle", {
    cx: "54",
    cy: "21",
    r: "3.5",
    fill: "var(--sulfur)"
  }));
  if (kind === "lens") return /*#__PURE__*/React.createElement("svg", {
    width: "88",
    height: "72",
    viewBox: "0 0 88 72",
    fill: "none",
    "aria-hidden": "true"
  }, /*#__PURE__*/React.createElement("circle", {
    cx: "38",
    cy: "30",
    r: "16",
    stroke: stroke,
    strokeWidth: "1.5"
  }), /*#__PURE__*/React.createElement("circle", {
    cx: "38",
    cy: "30",
    r: "16",
    fill: "var(--indigo)",
    opacity: ".08"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M50 42 L64 58",
    stroke: stroke,
    strokeWidth: "1.5",
    strokeLinecap: "round"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M62 56 l6 6",
    stroke: "var(--moss)",
    strokeWidth: "4",
    strokeLinecap: "round"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M31 27 c3 -5 9 -6 13 -3",
    stroke: stroke,
    strokeWidth: "1.2",
    strokeLinecap: "round"
  }));
  return /*#__PURE__*/React.createElement("svg", {
    width: "88",
    height: "72",
    viewBox: "0 0 88 72",
    fill: "none",
    "aria-hidden": "true"
  }, /*#__PURE__*/React.createElement("rect", {
    x: "20",
    y: "12",
    width: "42",
    height: "52",
    rx: "2",
    stroke: stroke,
    strokeWidth: "1.5"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M20 18 h-4 M20 30 h-4 M20 42 h-4 M20 54 h-4",
    stroke: "var(--moss)",
    strokeWidth: "2",
    strokeLinecap: "round"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M28 24 h26 M28 32 h26 M28 40 h16",
    stroke: stroke,
    strokeWidth: "1.2",
    strokeLinecap: "round",
    opacity: ".55"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "40",
    y: "48",
    width: "14",
    height: "9",
    fill: "var(--sulfur)",
    transform: "rotate(-2 47 52)"
  }));
}
function EmptyState({
  title,
  description,
  actionLabel,
  onAction,
  illustration = "page",
  style
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      textAlign: "center",
      gap: 8,
      padding: "40px 24px",
      ...style
    }
  }, /*#__PURE__*/React.createElement(Art, {
    kind: illustration
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 16,
      fontWeight: 600,
      color: "var(--ink)",
      marginTop: 8
    }
  }, title), description && /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 13,
      lineHeight: 1.6,
      color: "var(--ink-2)",
      maxWidth: "26em"
    }
  }, description), actionLabel && onAction && /*#__PURE__*/React.createElement("button", {
    onClick: onAction,
    style: {
      marginTop: 8,
      background: "var(--sulfur)",
      color: "var(--ink)",
      border: "1px solid var(--ink)",
      borderRadius: "var(--r-data)",
      boxShadow: "2px 2px 0 rgba(27,42,46,.18)",
      padding: "9px 18px",
      fontFamily: "var(--font-body)",
      fontWeight: 600,
      fontSize: 14,
      cursor: "pointer"
    }
  }, actionLabel));
}
Object.assign(__ds_scope, { EmptyState });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/status/EmptyState.jsx", error: String((e && e.message) || e) }); }

// components/status/SealedBlock.jsx
try { (() => {
/* 保护只读：装订线缝住的一页。侧边缝线纹 + 不存在编辑控件。 */
function SealedBlock({
  label = "装订 · 只读",
  children,
  style
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      position: "relative",
      background: "var(--moss-soft)",
      backgroundImage: "var(--tex-paper)",
      border: "1px solid rgba(107,122,90,.4)",
      borderRadius: "var(--r-data)",
      padding: "16px 20px 16px 30px",
      ...style
    }
  }, /*#__PURE__*/React.createElement("span", {
    "aria-hidden": "true",
    style: {
      position: "absolute",
      left: 10,
      top: 6,
      bottom: 6,
      width: 2,
      background: "var(--tex-stitch)"
    }
  }), /*#__PURE__*/React.createElement("span", {
    "aria-hidden": "true",
    style: {
      position: "absolute",
      left: 6,
      top: 6,
      bottom: 6,
      width: 10,
      backgroundImage: "repeating-linear-gradient(180deg, transparent 0 5px, rgba(107,122,90,.5) 5px 6px, transparent 6px 14px)",
      backgroundPosition: "0 3px",
      opacity: 0.5,
      transform: "rotate(0.4deg)"
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: "var(--font-mono)",
      fontSize: 12,
      letterSpacing: "0.04em",
      color: "var(--moss)",
      marginBottom: 8
    }
  }, label), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 14,
      lineHeight: 1.6,
      color: "var(--ink)"
    }
  }, children));
}
Object.assign(__ds_scope, { SealedBlock });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/status/SealedBlock.jsx", error: String((e && e.message) || e) }); }

// components/status/StatusMark.jsx
try { (() => {
/* §5 状态标记体系。铁规：每个状态同时有非颜色载体（记号形状/边缘质地/字体/底纹）。 */
const DEFS = {
  verified: {
    label: "已证",
    color: "var(--indigo)",
    bg: "transparent",
    border: "1px solid var(--indigo)",
    mark: "square-solid"
  },
  review: {
    label: "待复核",
    color: "var(--indigo)",
    bg: "var(--indigo-soft)",
    bgImage: "var(--tex-note)",
    border: "1px solid rgba(46,74,125,.35)",
    mark: "square-hollow"
  },
  blocking: {
    label: "待处理",
    color: "var(--rust)",
    bg: "var(--rust-soft)",
    border: "1px double var(--rust)",
    borderWidth: 3,
    mark: "triangle"
  },
  disputed: {
    label: "争议",
    color: "var(--ink-2)",
    bg: "var(--paper-2)",
    bgImage: "var(--tex-hatch)",
    border: "1px solid var(--rule)",
    mark: "warn"
  },
  speculative: {
    label: "推测",
    color: "var(--ink-2)",
    bg: "transparent",
    border: "1.5px dashed var(--ink-3)",
    mark: "pencil",
    sketch: true
  },
  void: {
    label: "空缺",
    color: "var(--ink-3)",
    bg: "var(--paper-2)",
    border: "1px solid var(--rule)",
    emboss: true,
    mark: "none"
  },
  sealed: {
    label: "只读",
    color: "var(--moss)",
    bg: "var(--moss-soft)",
    border: "1px solid rgba(107,122,90,.4)",
    stitch: true,
    mark: "none"
  },
  degraded: {
    label: "降级生成",
    color: "var(--ink-3)",
    bg: "var(--surface)",
    bgImage: "var(--tex-halftone)",
    border: "1px solid var(--rule)",
    mark: "dot"
  }
};
function Mark({
  kind,
  color
}) {
  const s = {
    display: "inline-block",
    flex: "none"
  };
  if (kind === "square-solid") return /*#__PURE__*/React.createElement("span", {
    style: {
      ...s,
      width: 7,
      height: 7,
      background: color
    }
  });
  if (kind === "square-hollow") return /*#__PURE__*/React.createElement("span", {
    style: {
      ...s,
      width: 7,
      height: 7,
      border: `1.5px solid ${color}`,
      boxSizing: "border-box"
    }
  });
  if (kind === "triangle") return /*#__PURE__*/React.createElement("span", {
    style: {
      ...s,
      width: 0,
      height: 0,
      borderLeft: "5px solid transparent",
      borderRight: "5px solid transparent",
      borderBottom: `8px solid ${color}`
    }
  });
  if (kind === "warn") return /*#__PURE__*/React.createElement("span", {
    "aria-hidden": "true",
    style: {
      ...s,
      width: 9,
      height: 9,
      border: `1px solid ${color}`,
      backgroundImage: "var(--tex-hatch)",
      boxSizing: "border-box"
    }
  });
  if (kind === "pencil") return /*#__PURE__*/React.createElement("span", {
    style: {
      ...s,
      width: 10,
      height: 0,
      borderTop: `1.5px dashed ${color}`
    }
  });
  if (kind === "dot") return /*#__PURE__*/React.createElement("span", {
    style: {
      ...s,
      width: 8,
      height: 8,
      background: `radial-gradient(${color} 1px, transparent 1.4px) 0 0/4px 4px`
    }
  });
  return null;
}
function StatusMark({
  status,
  label,
  style
}) {
  const d = DEFS[status] || DEFS.verified;
  return /*#__PURE__*/React.createElement("span", {
    style: {
      position: "relative",
      display: "inline-flex",
      alignItems: "center",
      gap: 6,
      padding: d.stitch ? "2px 10px 2px 14px" : "2px 10px",
      borderRadius: d.sketch ? "6px 3px 7px 4px / 4px 7px 3px 6px" : "var(--r-data)",
      border: d.border,
      background: d.bg,
      backgroundImage: d.bgImage || "none",
      boxShadow: d.emboss ? "var(--emboss)" : "none",
      fontFamily: "var(--font-mono)",
      fontSize: 12,
      lineHeight: 1.6,
      letterSpacing: "0.02em",
      color: d.color,
      whiteSpace: "nowrap",
      ...style
    }
  }, d.stitch && /*#__PURE__*/React.createElement("span", {
    "aria-hidden": "true",
    style: {
      position: "absolute",
      left: 4,
      top: 2,
      bottom: 2,
      width: 2,
      background: "var(--tex-stitch)"
    }
  }), /*#__PURE__*/React.createElement(Mark, {
    kind: d.mark,
    color: d.color
  }), label || d.label);
}
Object.assign(__ds_scope, { StatusMark });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/status/StatusMark.jsx", error: String((e && e.message) || e) }); }

// components/status/VoidBlock.jsx
try { (() => {
/* 有形空缺：定高空区 + 压印纹理 + 标尺线。NEVER 用生成文字填满。 */
function VoidBlock({
  kind = "missing-data",
  height = 120,
  note,
  actionLabel,
  onAction,
  style
}) {
  const defs = {
    "missing-data": {
      tag: "资料缺口",
      text: note || "该部分资料缺失，暂无法判定。",
      action: actionLabel || "补充资料"
    },
    "no-access": {
      tag: "权限缺口",
      text: note || "你没有查看该部分的权限。",
      action: actionLabel || "申请权限"
    }
  };
  const d = defs[kind] || defs["missing-data"];
  return /*#__PURE__*/React.createElement("div", {
    style: {
      position: "relative",
      minHeight: height,
      background: "var(--paper-2)",
      backgroundImage: "var(--tex-press)",
      boxShadow: "var(--emboss)",
      border: "1px solid var(--rule)",
      borderRadius: "var(--r-data)",
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      gap: 8,
      padding: "16px 16px 16px 32px",
      ...style
    }
  }, /*#__PURE__*/React.createElement("span", {
    "aria-hidden": "true",
    style: {
      position: "absolute",
      left: 10,
      top: 8,
      bottom: 8,
      width: 8,
      backgroundImage: "repeating-linear-gradient(180deg, var(--ink-3) 0 1px, transparent 1px 8px)",
      opacity: 0.5
    }
  }), /*#__PURE__*/React.createElement("span", {
    "aria-hidden": "true",
    style: {
      position: "absolute",
      left: 10,
      top: 8,
      bottom: 8,
      width: 4,
      backgroundImage: "repeating-linear-gradient(180deg, var(--ink-3) 0 1px, transparent 1px 24px)"
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: "var(--font-mono)",
      fontSize: 12,
      letterSpacing: "0.04em",
      color: "var(--ink-3)"
    }
  }, d.tag), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 13,
      color: "var(--ink-2)",
      textAlign: "center",
      maxWidth: "26em"
    }
  }, d.text), onAction && /*#__PURE__*/React.createElement("button", {
    onClick: onAction,
    style: {
      background: "none",
      border: "none",
      cursor: "pointer",
      fontFamily: "var(--font-body)",
      fontSize: 13,
      color: "var(--indigo)",
      textDecoration: "underline",
      textUnderlineOffset: 3,
      padding: 2
    }
  }, d.action));
}
Object.assign(__ds_scope, { VoidBlock });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/status/VoidBlock.jsx", error: String((e && e.message) || e) }); }

// components/surfaces/PaperSurface.jsx
try { (() => {
function PaperSurface({
  tone = "surface",
  texture = true,
  padding = 24,
  radius = "card",
  border = true,
  children,
  style
}) {
  const bg = tone === "paper-2" ? "var(--paper-2)" : tone === "paper" ? "var(--paper)" : "var(--surface)";
  return /*#__PURE__*/React.createElement("div", {
    style: {
      background: bg,
      backgroundImage: texture ? "var(--tex-paper)" : "none",
      border: border ? "1px solid var(--rule)" : "none",
      borderRadius: radius === "data" ? "var(--r-data)" : "var(--r-card)",
      padding,
      ...style
    }
  }, children);
}
Object.assign(__ds_scope, { PaperSurface });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/surfaces/PaperSurface.jsx", error: String((e && e.message) || e) }); }

// components/surfaces/StickerTag.jsx
try { (() => {
function StickerTag({
  children,
  rotate = -1,
  tone = "paper",
  mono = true,
  style
}) {
  const tones = {
    paper: {
      background: "var(--paper-2)",
      color: "var(--ink-2)",
      border: "1px solid var(--rule)"
    },
    indigo: {
      background: "var(--indigo-soft)",
      color: "var(--indigo)",
      border: "1px solid rgba(46,74,125,.35)"
    },
    sulfur: {
      background: "var(--sulfur-soft)",
      color: "var(--ink)",
      border: "1px solid rgba(232,185,60,.8)"
    },
    moss: {
      background: "var(--moss-soft)",
      color: "var(--moss)",
      border: "1px solid rgba(107,122,90,.4)"
    }
  };
  const r = Math.max(-1.5, Math.min(1.5, rotate));
  return /*#__PURE__*/React.createElement("span", {
    style: {
      display: "inline-block",
      padding: "3px 12px",
      borderRadius: "var(--r-tag)",
      fontFamily: mono ? "var(--font-mono)" : "var(--font-body)",
      fontSize: 12,
      lineHeight: 1.5,
      letterSpacing: "0.02em",
      boxShadow: "var(--shadow-sticker)",
      transform: `rotate(${r}deg)`,
      ...tones[tone],
      ...style
    }
  }, children);
}
Object.assign(__ds_scope, { StickerTag });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/surfaces/StickerTag.jsx", error: String((e && e.message) || e) }); }

// ui_kits/app/leads.screen.jsx
try { (() => {
const {
  PaperSurface,
  StickerTag,
  StatusMark,
  ChannelValue,
  EmptyState,
  Button
} = window.FlintDesignSystem_8fd95b;
const flintLeads = [{
  id: "LD-2026-0801-014",
  title: "折叠屏换机潮：铰链降本触发中端下探",
  cat: "消费电子",
  count: "1,204",
  status: "verified",
  time: "09:00:12"
}, {
  id: "LD-2026-0801-015",
  title: "钛合金中框代工报价松动",
  cat: "供应链",
  count: "863",
  status: "review",
  time: "09:00:12"
}, {
  id: "LD-2026-0801-016",
  title: "线下渠道补贴或于 Q4 收紧",
  cat: "渠道",
  count: "512",
  status: "speculative",
  time: "09:00:13"
}];
function FlintLeadsScreen({
  onOpen
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 16
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "baseline",
      justifyContent: "space-between"
    }
  }, /*#__PURE__*/React.createElement("h1", {
    style: {
      fontFamily: "var(--font-display)",
      fontWeight: 400,
      fontSize: 25,
      margin: 0,
      color: "var(--ink)"
    }
  }, "\u4ECA\u65E5\u7EBF\u7D22"), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 13,
      color: "var(--ink-2)"
    }
  }, "\u91C7\u96C6\u5B8C\u6210\u4E8E ", /*#__PURE__*/React.createElement(ChannelValue, {
    channel: "fact",
    value: "09:00:14",
    style: {
      fontSize: 13
    }
  }))), /*#__PURE__*/React.createElement(PaperSurface, {
    padding: 0
  }, flintLeads.map((l, i) => /*#__PURE__*/React.createElement("div", {
    key: l.id,
    onClick: onOpen,
    role: "button",
    tabIndex: 0,
    onKeyDown: e => e.key === "Enter" && onOpen(),
    style: {
      display: "grid",
      gridTemplateColumns: "1fr auto auto auto",
      gap: 24,
      alignItems: "center",
      padding: "16px 24px",
      borderBottom: i < flintLeads.length - 1 ? "1px solid var(--rule)" : "none",
      cursor: "pointer"
    },
    onMouseEnter: e => e.currentTarget.style.background = "var(--paper-2)",
    onMouseLeave: e => e.currentTarget.style.background = "transparent"
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 14,
      fontWeight: 600,
      color: "var(--ink)",
      opacity: l.status === "speculative" ? 0.85 : 1
    }
  }, l.title), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 10,
      alignItems: "center",
      marginTop: 6
    }
  }, /*#__PURE__*/React.createElement(StickerTag, {
    rotate: i % 2 ? 1 : -1
  }, l.cat), /*#__PURE__*/React.createElement(ChannelValue, {
    channel: "self",
    value: l.id,
    style: {
      fontSize: 12
    },
    dim: true
  }))), /*#__PURE__*/React.createElement(ChannelValue, {
    channel: "fact",
    value: l.count,
    unit: "\u6761",
    style: {
      fontSize: 13
    }
  }), /*#__PURE__*/React.createElement(StatusMark, {
    status: l.status
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: "var(--font-mono)",
      fontVariantNumeric: "tabular-nums",
      fontSize: 12,
      color: "var(--ink-3)"
    }
  }, l.time)))), /*#__PURE__*/React.createElement(PaperSurface, {
    padding: 0
  }, /*#__PURE__*/React.createElement(EmptyState, {
    illustration: "lens",
    title: "\u6CA1\u6709\u66F4\u591A\u7EBF\u7D22",
    description: "\u4E0B\u4E00\u6B21\u91C7\u96C6\u5728\u660E\u65E5 09:00\uFF1B\u5386\u53F2\u7EBF\u7D22\u89C1\u5B58\u6863\u3002",
    style: {
      padding: "24px 16px"
    }
  })));
}
window.FlintLeadsScreen = FlintLeadsScreen;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/app/leads.screen.jsx", error: String((e && e.message) || e) }); }

// ui_kits/app/report.screen.jsx
try { (() => {
const {
  PaperSurface: FSurface,
  StickerTag: FTag,
  StatusMark: FMark,
  ChannelValue: FVal,
  CitationMark: FCite,
  DataTable: FTable,
  ChartPlaceholder: FChart,
  VoidBlock: FVoid,
  SealedBlock: FSealed,
  DegradedNotice: FDegraded,
  Button: FBtn,
  Dialog: FDialog
} = window.FlintDesignSystem_8fd95b;
function FlintReportScreen({
  onBack
}) {
  const [blocked, setBlocked] = React.useState(false);
  const [noteOpen, setNoteOpen] = React.useState(true);
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 16
    }
  }, /*#__PURE__*/React.createElement("button", {
    onClick: onBack,
    style: {
      alignSelf: "flex-start",
      background: "none",
      border: "none",
      cursor: "pointer",
      padding: 0,
      fontSize: 13,
      color: "var(--indigo)",
      textDecoration: "underline",
      textUnderlineOffset: 3
    }
  }, "\u2190 \u8FD4\u56DE\u4ECA\u65E5\u7EBF\u7D22"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "flex-start",
      justifyContent: "space-between",
      gap: 24
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("h1", {
    style: {
      fontFamily: "var(--font-display)",
      fontWeight: 400,
      fontSize: 31,
      lineHeight: 1.15,
      margin: 0,
      color: "var(--ink)"
    }
  }, "\u6298\u53E0\u5C4F\u6362\u673A\u6F6E\uFF1A\u53EF\u884C\u6027\u5224\u5B9A"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 10,
      alignItems: "center",
      marginTop: 10,
      flexWrap: "wrap"
    }
  }, /*#__PURE__*/React.createElement(FVal, {
    channel: "self",
    value: "RPT-2026-0801-003",
    style: {
      fontSize: 12
    }
  }), /*#__PURE__*/React.createElement(FTag, {
    rotate: 1
  }, "\u6D88\u8D39\u7535\u5B50"), /*#__PURE__*/React.createElement(FMark, {
    status: "verified",
    label: "\u5224\u5B9A\u5DF2\u8BC1"
  }), /*#__PURE__*/React.createElement(FMark, {
    status: "blocking",
    label: "1 \u9879\u5F85\u5904\u7406"
  }))), /*#__PURE__*/React.createElement(FBtn, {
    onClick: () => setBlocked(true)
  }, "\u5BFC\u51FA\u62A5\u544A")), /*#__PURE__*/React.createElement(FSurface, {
    padding: 28
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: "var(--font-mono)",
      fontSize: 12,
      letterSpacing: "0.04em",
      color: "var(--ink-3)",
      marginBottom: 10
    }
  }, "VERDICT \xB7 \u5224\u5B9A"), /*#__PURE__*/React.createElement("p", {
    style: {
      fontSize: 16,
      lineHeight: 1.8,
      margin: 0,
      maxWidth: "34em",
      color: "var(--ink)"
    }
  }, /*#__PURE__*/React.createElement("b", null, "\u53EF\u884C\u3002"), "\u8BDD\u9898\u63D0\u53CA\u91CF\u8FBE ", /*#__PURE__*/React.createElement(FVal, {
    channel: "fact",
    value: "1,204",
    unit: "\u6761"
  }), /*#__PURE__*/React.createElement(FCite, {
    index: 1,
    source: {
      title: "供应链周报",
      detail: "第 31 期 · 面板与铰链",
      id: "SRC-8841",
      date: "2026-07-28"
    }
  }), "\uFF0C \u94F0\u94FE\u5355\u4EF6\u62A5\u4EF7\u964D\u81F3 ", /*#__PURE__*/React.createElement(FVal, {
    channel: "price",
    value: "\xA5118"
  }), /*#__PURE__*/React.createElement(FCite, {
    index: 2,
    source: {
      title: "代工报价单",
      id: "SRC-8902",
      date: "2026-07-30"
    }
  }), "\uFF0C \u6211\u65B9\u76F8\u5173\u7EBF\u7D22 ", /*#__PURE__*/React.createElement(FVal, {
    channel: "self",
    value: "3",
    unit: "\u6761"
  }), /*#__PURE__*/React.createElement(FCite, {
    index: 3,
    source: null
  }), "\u3002\u6570\u91CF\u4E0E\u5355\u4EF7\u5206\u5217\uFF0C\u4E0D\u5408\u5E76\u8BA1\u7B97\u3002")), noteOpen ? /*#__PURE__*/React.createElement("div", {
    style: {
      background: "var(--indigo-soft)",
      backgroundImage: "var(--tex-note)",
      border: "1px solid rgba(46,74,125,.35)",
      borderRadius: "var(--r-data)",
      padding: "12px 16px",
      display: "flex",
      gap: 12,
      alignItems: "flex-start"
    }
  }, /*#__PURE__*/React.createElement("span", {
    "aria-hidden": "true",
    style: {
      flex: "none",
      marginTop: 6,
      width: 7,
      height: 7,
      border: "1.5px solid var(--indigo)",
      boxSizing: "border-box"
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: "var(--font-mono)",
      fontSize: 12,
      letterSpacing: "0.04em",
      color: "var(--indigo)"
    }
  }, "\u5F85\u590D\u6838 \xB7 \u63D0\u793A\u7EA7"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 13,
      lineHeight: 1.6,
      color: "var(--ink-2)",
      marginTop: 2
    }
  }, "\u300C\u6E20\u9053\u8865\u8D34\u6536\u7D27\u300D\u4E00\u8282\u5F15\u7528\u7684\u4E24\u6761\u6765\u6E90\u65F6\u95F4\u76F8\u5DEE 6 \u5929\uFF0C\u5EFA\u8BAE\u4EBA\u5DE5\u6838\u5BF9\u53E3\u5F84\u3002")), /*#__PURE__*/React.createElement("button", {
    onClick: () => setNoteOpen(false),
    style: {
      background: "none",
      border: "none",
      cursor: "pointer",
      fontFamily: "var(--font-mono)",
      fontSize: 12,
      color: "var(--indigo)",
      padding: 2
    }
  }, "\u6298\u53E0")) : /*#__PURE__*/React.createElement("button", {
    onClick: () => setNoteOpen(true),
    style: {
      alignSelf: "flex-start",
      background: "none",
      border: "none",
      cursor: "pointer",
      padding: 0,
      fontFamily: "var(--font-mono)",
      fontSize: 12,
      color: "var(--indigo)",
      textDecoration: "underline",
      textUnderlineOffset: 3
    }
  }, "\u5C55\u5F00 1 \u6761\u4FBF\u6761"), /*#__PURE__*/React.createElement(FTable, {
    caption: "\u4FE1\u53F7\u6C47\u603B \xB7 2026-08-01",
    columns: [{
      key: "n",
      label: "信号"
    }, {
      key: "id",
      label: "ID",
      channel: "self"
    }, {
      key: "c",
      label: "提及量",
      channel: "fact",
      unit: "条"
    }, {
      key: "p",
      label: "指导价",
      channel: "price"
    }],
    rows: [{
      n: "折叠屏换机潮",
      id: "LD-014",
      c: "1,204",
      p: "¥7,999"
    }, {
      n: "钛合金中框降本",
      id: "LD-015",
      c: "863",
      p: "¥4,599"
    }, {
      n: "线下渠道补贴",
      id: "LD-016",
      c: "512",
      p: "¥1,299"
    }]
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "1fr 1fr",
      gap: 16,
      alignItems: "start"
    }
  }, /*#__PURE__*/React.createElement(FChart, {
    title: "\u63D0\u53CA\u91CF \xB7 7 \u65E5",
    height: 150,
    sourceNote: "\u6570\u503C\u89C1\u300C\u4FE1\u53F7\u6C47\u603B\u300D\u8868\uFF0C\u51FA\u5904 SRC-8841\u3002"
  }), /*#__PURE__*/React.createElement(FVoid, {
    kind: "missing-data",
    height: 150,
    note: "\u7ADE\u54C1\u6E20\u9053\u6210\u672C\u8D44\u6599\u7F3A\u5931\uFF0C\u672C\u8282\u7559\u7A7A\u3002",
    onAction: () => {}
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      border: "1.5px dashed var(--ink-3)",
      borderRadius: "6px 3px 7px 4px / 4px 7px 3px 6px",
      padding: "16px 20px",
      maxWidth: "40em"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: "var(--font-mono)",
      fontSize: 12,
      letterSpacing: "0.04em",
      color: "var(--ink-2)",
      marginBottom: 6
    }
  }, "\u63A8\u6D4B \xB7 \u65E0\u8BC1\u636E\uFF0C\u4E0D\u63D0\u4F9B\u6EAF\u6E90"), /*#__PURE__*/React.createElement("p", {
    style: {
      margin: 0,
      fontSize: 14,
      lineHeight: 1.6,
      color: "var(--ink-2)"
    }
  }, "\u82E5\u8865\u8D34\u6536\u7D27\u4E0E\u94F0\u94FE\u964D\u672C\u540C\u5B63\u53D1\u751F\uFF0C\u4E2D\u7AEF\u6298\u53E0\u5C4F\u53EF\u80FD\u63D0\u524D\u8FDB\u5165\u4EF7\u683C\u6218\u3002\u6B64\u6BB5\u4E3A\u94C5\u7B14\u7A3F\uFF0C\u5BFC\u51FA\u65F6\u9ED8\u8BA4\u4E0D\u542B\u3002")), /*#__PURE__*/React.createElement(FDegraded, null, "\u4EF7\u683C\u901A\u9053\u6570\u636E\u6E90\u4E8E 07-31 \u77ED\u6682\u8D85\u65F6\uFF0C\u8868\u4E2D\u300C\u6307\u5BFC\u4EF7\u300D\u5217\u6309\u6700\u8FD1\u4E00\u6B21\u6210\u529F\u6293\u53D6\u751F\u6210\u3002"), /*#__PURE__*/React.createElement(FSealed, null, "\u5224\u5B9A\u300C\u53EF\u884C\u300D\u5DF2\u968F\u62A5\u544A v1.0 \u51BB\u7ED3\u4E8E 2026-08-01 09:41\uFF0C\u51FA\u5904\u94FE\u4E00\u5E76\u5C01\u5B58\u3002"), /*#__PURE__*/React.createElement(FDialog, {
    open: blocked,
    onClose: () => setBlocked(false),
    title: "\u5BFC\u51FA\u88AB\u963B\u65AD",
    footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(FBtn, {
      variant: "secondary",
      onClick: () => setBlocked(false)
    }, "\u7A0D\u540E\u5904\u7406"), /*#__PURE__*/React.createElement(FBtn, {
      onClick: () => setBlocked(false)
    }, "\u53BB\u590D\u6838"))
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 12,
      alignItems: "flex-start"
    }
  }, /*#__PURE__*/React.createElement(FMark, {
    status: "blocking",
    label: "HTTP 409"
  }), /*#__PURE__*/React.createElement("span", null, "\u5B58\u5728 ", /*#__PURE__*/React.createElement(FVal, {
    channel: "fact",
    value: "1",
    unit: "\u9879"
  }), " \u963B\u585E\u7EA7\u590D\u6838\u672A\u5904\u7406\uFF1A\u300C\u6E20\u9053\u8865\u8D34\u6536\u7D27\u300D\u6765\u6E90\u53E3\u5F84\u5F85\u786E\u8BA4\u3002\u5904\u7406\u5B8C\u6210\u524D\uFF0C\u62A5\u544A\u4E0D\u53EF\u5BFC\u51FA\u3002"))));
}
window.FlintReportScreen = FlintReportScreen;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/app/report.screen.jsx", error: String((e && e.message) || e) }); }

// ui_kits/marketing/landing.screen.jsx
try { (() => {
const {
  Button,
  StickerTag,
  PaperSurface,
  StatusMark,
  ChannelValue,
  CitationMark
} = window.FlintDesignSystem_8fd95b;
function useReveal() {
  React.useEffect(() => {
    const els = document.querySelectorAll(".reveal");
    const io = new IntersectionObserver(es => es.forEach(e => {
      if (e.isIntersecting) {
        e.target.classList.add("on");
        io.unobserve(e.target);
      }
    }), {
      threshold: 0.15
    });
    els.forEach(el => io.observe(el));
    return () => io.disconnect();
  }, []);
}
function SparkArt() {
  return /*#__PURE__*/React.createElement("svg", {
    width: "360",
    height: "320",
    viewBox: "0 0 360 320",
    fill: "none",
    "aria-hidden": "true",
    style: {
      maxWidth: "100%",
      height: "auto"
    }
  }, /*#__PURE__*/React.createElement("rect", {
    x: "60",
    y: "48",
    width: "200",
    height: "240",
    rx: "4",
    fill: "var(--surface)",
    stroke: "var(--indigo)",
    strokeWidth: "2",
    transform: "rotate(-2 160 168)"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M84 92 h150 M84 118 h150 M84 144 h96",
    stroke: "var(--indigo)",
    strokeWidth: "2",
    strokeLinecap: "round",
    opacity: ".45",
    transform: "rotate(-2 160 168)"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "84",
    y: "176",
    width: "150",
    height: "76",
    fill: "var(--paper-2)",
    transform: "rotate(-2 160 168)"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M96 236 c14 -22 34 -22 46 -6 c10 -26 34 -30 48 -12",
    stroke: "var(--moss)",
    strokeWidth: "2.5",
    strokeLinecap: "round",
    fill: "none",
    transform: "rotate(-2 160 168)"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "176",
    y: "30",
    width: "86",
    height: "26",
    rx: "13",
    fill: "var(--paper-2)",
    stroke: "var(--rule)",
    transform: "rotate(3 219 43)"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M262 214 L296 196 L286 180 L322 158",
    stroke: "var(--ink)",
    strokeWidth: "2.5",
    strokeLinecap: "round",
    strokeLinejoin: "round",
    fill: "none"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M326 150 l8 -14 M334 162 l16 -5 M330 174 l12 8 M316 142 l-2 -16",
    stroke: "var(--sulfur)",
    strokeWidth: "4",
    strokeLinecap: "round"
  }), /*#__PURE__*/React.createElement("circle", {
    cx: "322",
    cy: "155",
    r: "7",
    fill: "var(--sulfur)"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "236",
    y: "244",
    width: "72",
    height: "30",
    rx: "2",
    fill: "none",
    stroke: "var(--indigo)",
    strokeWidth: "2",
    transform: "rotate(-6 272 259)"
  }), /*#__PURE__*/React.createElement("text", {
    x: "248",
    y: "264",
    fontFamily: "var(--font-mono)",
    fontSize: "13",
    fill: "var(--indigo)",
    transform: "rotate(-6 272 259)"
  }, "\u5DF2\u8BC1 \u25A0"));
}
function FlintLanding() {
  useReveal();
  const d = i => ({
    animationDelay: `${0.12 * i}s`
  });
  return /*#__PURE__*/React.createElement("div", {
    style: {
      minHeight: "100vh"
    }
  }, /*#__PURE__*/React.createElement("header", {
    className: "enter",
    style: {
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      padding: "20px 48px",
      ...d(0)
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: "var(--font-display)",
      fontSize: 25,
      color: "var(--ink)"
    }
  }, "Flint \u71E7\u77F3"), /*#__PURE__*/React.createElement("nav", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 24
    }
  }, /*#__PURE__*/React.createElement("a", {
    href: "#how",
    style: {
      fontSize: 14
    }
  }, "\u5B83\u600E\u4E48\u5DE5\u4F5C"), /*#__PURE__*/React.createElement("a", {
    href: "#honest",
    style: {
      fontSize: 14
    }
  }, "\u5982\u5B9E\u539F\u5219"), /*#__PURE__*/React.createElement(Button, {
    size: "sm"
  }, "\u5F00\u59CB\u4F7F\u7528"))), /*#__PURE__*/React.createElement("section", {
    style: {
      display: "grid",
      gridTemplateColumns: "1.2fr 1fr",
      gap: 48,
      alignItems: "center",
      padding: "64px 48px 96px",
      maxWidth: 1280,
      margin: "0 auto",
      boxSizing: "border-box"
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "enter",
    style: d(1)
  }, /*#__PURE__*/React.createElement(StickerTag, {
    tone: "sulfur",
    rotate: -1.5
  }, "\u6BCF\u65E5 09:00 \u91C7\u96C6")), /*#__PURE__*/React.createElement("h1", {
    className: "enter",
    style: {
      fontFamily: "var(--font-display)",
      fontWeight: 400,
      fontSize: 96,
      lineHeight: 1.15,
      margin: "20px 0 0",
      color: "var(--ink)",
      ...d(2)
    }
  }, "\u628A\u6BCF\u65E5\u70ED\u70B9\uFF0C", /*#__PURE__*/React.createElement("br", null), "\u6572\u51FA", /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--indigo)"
    }
  }, "\u53EF\u884C\u7684"), /*#__PURE__*/React.createElement("span", {
    style: {
      background: "linear-gradient(transparent 62%, var(--sulfur) 62% 94%, transparent 94%)"
    }
  }, "\u706B\u82B1"), "\u3002"), /*#__PURE__*/React.createElement("p", {
    className: "enter",
    style: {
      fontSize: 16,
      lineHeight: 1.8,
      color: "var(--ink-2)",
      maxWidth: "30em",
      margin: "24px 0 0",
      ...d(3)
    }
  }, "Flint \u628A\u70ED\u70B9\u7EBF\u7D22\u6C89\u6DC0\u6210\u53EF\u884C\u6027\u5224\u5B9A\u4E0E\u6DF1\u5EA6\u62A5\u544A\u3002\u77E5\u9053\u4EC0\u4E48\u5C31\u8BF4\u4EC0\u4E48\uFF0C\u4E0D\u77E5\u9053\u5C31\u660E\u8BF4\u2014\u2014\u6BCF\u4E2A\u6570\u5B57\u90FD\u5E26\u51FA\u5904\uFF0C\u6BCF\u4E2A\u7A7A\u7F3A\u90FD\u7559\u7740\u5F62\u72B6\u3002"), /*#__PURE__*/React.createElement("div", {
    className: "enter",
    style: {
      display: "flex",
      gap: 16,
      marginTop: 32,
      ...d(4)
    }
  }, /*#__PURE__*/React.createElement(Button, null, "\u5F00\u59CB\u4F7F\u7528"), /*#__PURE__*/React.createElement(Button, {
    variant: "ghost"
  }, "\u770B\u4E00\u4EFD\u6837\u4F8B\u62A5\u544A"))), /*#__PURE__*/React.createElement("div", {
    className: "enter",
    style: {
      justifySelf: "center",
      ...d(5)
    }
  }, /*#__PURE__*/React.createElement(SparkArt, null))), /*#__PURE__*/React.createElement("section", {
    id: "how",
    style: {
      background: "var(--paper-2)",
      backgroundImage: "var(--tex-paper)",
      borderTop: "1px solid var(--rule)",
      borderBottom: "1px solid var(--rule)",
      padding: "96px 48px"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: 1184,
      margin: "0 auto"
    }
  }, /*#__PURE__*/React.createElement("h2", {
    className: "reveal",
    style: {
      fontFamily: "var(--font-display)",
      fontWeight: 400,
      fontSize: 48,
      lineHeight: 1.15,
      margin: 0,
      color: "var(--ink)"
    }
  }, "\u4E09\u6B65\uFF0C\u4ECE\u566A\u97F3\u5230\u5224\u5B9A"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "repeat(3,1fr)",
      gap: 24,
      marginTop: 48
    }
  }, [{
    n: "01",
    t: "采集线索",
    p: "从公开热点里收集当日线索，原样留存来源与时间戳。",
    tag: "SOURCE"
  }, {
    n: "02",
    t: "可行性判定",
    p: "只给布尔与枚举，不造分数。证据不足就标「推测」，缺口就留白。",
    tag: "VERDICT"
  }, {
    n: "03",
    t: "深度报告",
    p: "已证事实盖印冻结，随附出处链；表是真相，图只是摘要。",
    tag: "REPORT"
  }].map((c, i) => /*#__PURE__*/React.createElement("div", {
    className: "reveal",
    key: c.n,
    style: {
      transitionDelay: `${i * 0.1}s`
    }
  }, /*#__PURE__*/React.createElement(PaperSurface, {
    padding: 28,
    style: {
      height: "100%",
      boxSizing: "border-box"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      justifyContent: "space-between",
      alignItems: "baseline"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: "var(--font-mono)",
      fontVariantNumeric: "tabular-nums",
      fontSize: 13,
      color: "var(--indigo)"
    }
  }, c.n), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: "var(--font-mono)",
      fontSize: 12,
      letterSpacing: "0.04em",
      color: "var(--ink-3)"
    }
  }, c.tag)), /*#__PURE__*/React.createElement("h3", {
    style: {
      fontSize: 20,
      margin: "14px 0 8px",
      color: "var(--ink)"
    }
  }, c.t), /*#__PURE__*/React.createElement("p", {
    style: {
      fontSize: 14,
      lineHeight: 1.6,
      color: "var(--ink-2)",
      margin: 0
    }
  }, c.p))))))), /*#__PURE__*/React.createElement("section", {
    id: "honest",
    style: {
      padding: "96px 48px",
      maxWidth: 1184,
      margin: "0 auto",
      boxSizing: "border-box"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "1fr 1.1fr",
      gap: 48,
      alignItems: "center"
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "reveal"
  }, /*#__PURE__*/React.createElement("h2", {
    style: {
      fontFamily: "var(--font-display)",
      fontWeight: 400,
      fontSize: 48,
      lineHeight: 1.15,
      margin: 0,
      color: "var(--ink)"
    }
  }, "\u77E5\u9053\u4EC0\u4E48\uFF0C", /*#__PURE__*/React.createElement("br", null), "\u5C31\u8BF4\u4EC0\u4E48\u3002"), /*#__PURE__*/React.createElement("p", {
    style: {
      fontSize: 16,
      lineHeight: 1.8,
      color: "var(--ink-2)",
      maxWidth: "28em",
      marginTop: 20
    }
  }, "\u53EF\u9760\u5EA6\u4E0D\u662F\u8FDB\u5EA6\u6761\u3002Flint \u7528\u4E00\u5957\u76D6\u5370\u3001\u4FBF\u6761\u4E0E\u94C5\u7B14\u7A3F\u7684\u8BB0\u53F7\u4F53\u7CFB\uFF0C\u628A\u6BCF\u6761\u5185\u5BB9\u7684\u628A\u63E1\u7A0B\u5EA6\u5199\u5728\u7EB8\u9762\u4E0A\u3002"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 10,
      flexWrap: "wrap",
      marginTop: 24
    }
  }, /*#__PURE__*/React.createElement(StatusMark, {
    status: "verified"
  }), /*#__PURE__*/React.createElement(StatusMark, {
    status: "review"
  }), /*#__PURE__*/React.createElement(StatusMark, {
    status: "speculative"
  }), /*#__PURE__*/React.createElement(StatusMark, {
    status: "sealed"
  }))), /*#__PURE__*/React.createElement("div", {
    className: "reveal",
    style: {
      transitionDelay: ".1s"
    }
  }, /*#__PURE__*/React.createElement(PaperSurface, {
    padding: 28,
    style: {
      transform: "rotate(0.6deg)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center",
      marginBottom: 12
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: "var(--font-mono)",
      fontSize: 12,
      letterSpacing: "0.04em",
      color: "var(--ink-3)"
    }
  }, "REPORT \xB7 \u6458\u5F55"), /*#__PURE__*/React.createElement(StatusMark, {
    status: "verified"
  })), /*#__PURE__*/React.createElement("p", {
    style: {
      fontSize: 16,
      lineHeight: 1.8,
      margin: 0,
      color: "var(--ink)"
    }
  }, "\u6298\u53E0\u5C4F\u8BDD\u9898\u63D0\u53CA\u91CF\u8FBE ", /*#__PURE__*/React.createElement(ChannelValue, {
    channel: "fact",
    value: "1,204",
    unit: "\u6761"
  }), /*#__PURE__*/React.createElement(CitationMark, {
    index: 1,
    source: {
      title: "供应链周报",
      id: "SRC-8841",
      date: "2026-07-28"
    }
  }), "\uFF0C \u4E3B\u6D41\u673A\u578B\u6307\u5BFC\u4EF7 ", /*#__PURE__*/React.createElement(ChannelValue, {
    channel: "price",
    value: "\xA57,999"
  }), /*#__PURE__*/React.createElement(CitationMark, {
    index: 2,
    source: null
  }), "\u3002"))))), /*#__PURE__*/React.createElement("footer", {
    style: {
      borderTop: "1px solid var(--rule)",
      padding: "32px 48px",
      display: "flex",
      justifyContent: "space-between",
      alignItems: "baseline"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: "var(--font-display)",
      fontSize: 20,
      color: "var(--ink-2)"
    }
  }, "Flint \u71E7\u77F3"), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: "var(--font-mono)",
      fontSize: 12,
      color: "var(--ink-3)"
    }
  }, "\u6BCF\u65E5\u70ED\u70B9 \u2192 \u53EF\u884C\u6027\u5224\u5B9A \u2192 \u6DF1\u5EA6\u62A5\u544A")));
}
window.FlintLanding = FlintLanding;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/marketing/landing.screen.jsx", error: String((e && e.message) || e) }); }

__ds_ns.Button = __ds_scope.Button;

__ds_ns.Dialog = __ds_scope.Dialog;

__ds_ns.Input = __ds_scope.Input;

__ds_ns.Tabs = __ds_scope.Tabs;

__ds_ns.ChannelValue = __ds_scope.ChannelValue;

__ds_ns.CitationMark = __ds_scope.CitationMark;

__ds_ns.DataTable = __ds_scope.DataTable;

__ds_ns.ChartPlaceholder = __ds_scope.ChartPlaceholder;

__ds_ns.DegradedNotice = __ds_scope.DegradedNotice;

__ds_ns.EmptyState = __ds_scope.EmptyState;

__ds_ns.SealedBlock = __ds_scope.SealedBlock;

__ds_ns.StatusMark = __ds_scope.StatusMark;

__ds_ns.VoidBlock = __ds_scope.VoidBlock;

__ds_ns.PaperSurface = __ds_scope.PaperSurface;

__ds_ns.StickerTag = __ds_scope.StickerTag;

})();
