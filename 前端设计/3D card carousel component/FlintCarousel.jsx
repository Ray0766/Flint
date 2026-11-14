/* Flint 化 3D 报告轮播 — 数学结构改编自用户提供的 Animated Cards demo */
const { useState, useEffect, useRef } = React;

const REPORTS = [
  { id: "RPT-0731", tag: "深度报告", tone: "sulfur", title: "车规激光雷达跌破千元档", verdict: "可行", facts: "3", date: "2026-07-31", src: "SRC-9021" },
  { id: "RPT-0728", tag: "深度报告", tone: "indigo", title: "折叠屏中框供应吃紧", verdict: "观望", facts: "2", date: "2026-07-28", src: "SRC-8841" },
  { id: "RPT-0724", tag: "深度报告", tone: "moss", title: "县域即时零售补贴战降温", verdict: "可行", facts: "4", date: "2026-07-24", src: "SRC-8710" },
  { id: "RPT-0722", tag: "深度报告", tone: "indigo", title: "固态电池中试线提前投产", verdict: "观望", facts: "2", date: "2026-07-22", src: "SRC-8695" },
  { id: "RPT-0718", tag: "深度报告", tone: "paper", title: "跨境小包新税则落地", verdict: "可行", facts: "3", date: "2026-07-18", src: "SRC-8512" },
];

const TAG_TONES = {
  paper: { background: "var(--paper-2)", color: "var(--ink-2)", border: "1px solid var(--rule)" },
  indigo: { background: "var(--indigo-soft)", color: "var(--indigo)", border: "1px solid rgba(46,74,125,.35)" },
  sulfur: { background: "var(--sulfur-soft)", color: "var(--ink)", border: "1px solid rgba(232,185,60,.8)" },
  moss: { background: "var(--moss-soft)", color: "var(--moss)", border: "1px solid rgba(107,122,90,.4)" },
};

function CardFront({ r }) {
  return (
    <div style={{ position: "absolute", inset: 0, padding: "1.25em", boxSizing: "border-box", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <span style={{ display: "inline-block", padding: "0.2em 0.85em", borderRadius: 999, fontFamily: "var(--font-mono)", fontSize: "0.75em", lineHeight: 1.5, letterSpacing: "0.02em", boxShadow: "var(--shadow-sticker)", transform: "rotate(-1.2deg)", ...TAG_TONES[r.tone] }}>{r.tag}</span>
        <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.7em", letterSpacing: "0.04em", color: "var(--ink-3)" }}>REPORT</span>
      </div>
      <div style={{ fontSize: "1.45em", lineHeight: 1.35, color: "var(--ink)", fontWeight: 600, letterSpacing: 0 }}>{r.title}</div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.35em" }}>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.72em", color: "var(--indigo)" }}>■ 已证 ×{r.facts}</span>
          <span style={{ fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums", fontSize: "0.72em", color: "var(--ink-3)" }}>{r.id} · {r.date}</span>
        </div>
        <span aria-hidden="true" style={{ width: "1.9em", height: "1.9em", border: "1.5px solid var(--indigo)", borderRadius: 2, color: "var(--indigo)", fontFamily: "var(--font-display)", fontSize: "1em", display: "flex", alignItems: "center", justifyContent: "center", transform: "rotate(2deg)", opacity: 0.85 }}>燧</span>
      </div>
    </div>
  );
}

function CardBack({ r }) {
  return (
    <div style={{ position: "absolute", inset: 0, padding: "1.25em", boxSizing: "border-box", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.7em", letterSpacing: "0.04em", color: "var(--ink-3)" }}>VERDICT</span>
        <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.7em", color: "var(--ink-3)" }}>{r.id}</span>
      </div>
      <div>
        <div style={{ fontFamily: "var(--font-display)", fontSize: "2em", lineHeight: 1.15, color: r.verdict === "可行" ? "var(--indigo)" : "var(--ink-2)" }}>{r.verdict}</div>
        <div style={{ fontSize: "0.82em", lineHeight: 1.7, color: "var(--ink-2)", marginTop: "0.5em" }}>该判定基于 <span style={{ fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums", color: "var(--ink)" }}>{r.facts}</span> 条已证事实。</div>
      </div>
      <div style={{ fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums", fontSize: "0.7em", color: "var(--ink-3)" }}>{r.src} · {r.date} 盖印冻结</div>
    </div>
  );
}

function FlintCarousel({ speed = 1, tilt = true }) {
  const cardCount = REPORTS.length;
  const containerRef = useRef(null);
  const cardsRefs = useRef([]);
  const frameId = useRef(0);
  const progress = useRef(0);
  const mouse = useRef({ x: 0, y: 0, targetX: 0, targetY: 0 });
  const [metrics, setMetrics] = useState({ cardW: 360, cardH: 226 });
  const reduced = useRef(false);

  useEffect(() => {
    reduced.current = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const handleMouseMove = (e) => {
      const rx = (e.clientX - window.innerWidth / 2) / (window.innerWidth / 2);
      const ry = (e.clientY - window.innerHeight / 2) / (window.innerHeight / 2);
      mouse.current.targetX = Math.max(-1, Math.min(1, rx));
      mouse.current.targetY = Math.max(-1, Math.min(1, ry));
    };
    const handleMouseLeave = () => { mouse.current.targetX = 0; mouse.current.targetY = 0; };
    window.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseleave", handleMouseLeave);
    return () => { window.removeEventListener("mousemove", handleMouseMove); document.removeEventListener("mouseleave", handleMouseLeave); };
  }, []);

  useEffect(() => {
    const handleResize = () => {
      const el = containerRef.current;
      if (!el) return;
      const w = el.clientWidth, h = el.clientHeight;
      let cardW = Math.min(380, Math.max(230, Math.round(w * 0.62)));
      cardW = Math.round(cardW * Math.min(1, Math.max(0.65, h / 700)));
      setMetrics({ cardW, cardH: Math.round(cardW / 1.5925) });
    };
    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  const renderLoop = () => {
    if (!reduced.current) progress.current += 0.0016 * (speed || 0);
    const damp = tilt && !reduced.current ? 0.08 : 0;
    if (damp) {
      mouse.current.x += (mouse.current.targetX - mouse.current.x) * damp;
      mouse.current.y += (mouse.current.targetY - mouse.current.y) * damp;
    } else { mouse.current.x = 0; mouse.current.y = 0; }

    const el = containerRef.current;
    if (!el) return;
    const h = el.clientHeight;
    const { cardH } = metrics;
    const cards = cardsRefs.current;

    const continuousProgress = progress.current;
    const roundedIndex = Math.round(continuousProgress);
    const diffFromRound = continuousProgress - roundedIndex;
    // 磁性驻留：正面在中心停一拍，再加速翻向下一张
    const easedDiff = Math.sign(diffFromRound) * Math.pow(Math.abs(diffFromRound) * 2, 4.2) / 2;
    const virtualActiveIndex = roundedIndex + easedDiff;

    for (let i = 0; i < cardCount; i++) {
      const card = cards[i];
      if (!card) continue;
      let offset = i - virtualActiveIndex;
      const halfCount = cardCount / 2;
      while (offset > halfCount) offset -= cardCount;
      while (offset < -halfCount) offset += cardCount;
      const absOffset = Math.abs(offset);
      const sign = Math.sign(offset);

      if (absOffset > 3.0) { card.style.visibility = "hidden"; continue; }
      card.style.visibility = "visible";

      const gap = 32;
      const peekAmount = -55;
      const D = 1350;
      let y = 0, z = 0, rot = 0;

      if (absOffset <= 1) {
        const t = absOffset, easedT = t * t * (3 - 2 * t);
        y = -sign * (easedT * (cardH + gap));
        z = 400 + easedT * (220 - 400);
        rot = easedT * 132;
      } else if (absOffset <= 2) {
        const t = absOffset - 1, easedT = t * t * (3 - 2 * t);
        const yStart = cardH + gap, zStart = 220, rotStart = 132, zEnd = -60, rotEnd = 175;
        const sEnd = D / (D - zEnd);
        const yEnd = (h / 2 - peekAmount) / sEnd - cardH / 2;
        y = -sign * (yStart + easedT * (yEnd - yStart));
        z = zStart + easedT * (zEnd - zStart);
        rot = rotStart + easedT * (rotEnd - rotStart);
      } else {
        const t = Math.min(absOffset - 2, 1), easedT = t * t * (3 - 2 * t);
        const zStart = -60, rotStart = 175, zEnd3 = -250, rotEnd3 = 195;
        const sEnd2 = D / (D - zStart);
        const yEnd2 = (h / 2 - peekAmount) / sEnd2 - cardH / 2;
        const sEnd3 = D / (D - zEnd3);
        const yEnd3 = (h / 2 + 100) / sEnd3 + cardH / 2;
        y = -sign * (yEnd2 + easedT * (yEnd3 - yEnd2));
        z = zStart + easedT * (zEnd3 - zStart);
        rot = rotStart + easedT * (rotEnd3 - rotStart);
      }

      const localCardRotation = -sign * rot;
      const centerFactor = Math.max(0, 1 - absOffset);
      const totalRotX = localCardRotation + -mouse.current.y * 12 * centerFactor;
      const totalRotY = mouse.current.x * 15 * centerFactor;

      card.style.zIndex = Math.round(z).toString();
      card.style.transform = `translateY(${y.toFixed(2)}px) translateZ(${z.toFixed(2)}px) rotateX(${totalRotX.toFixed(2)}deg) rotateY(${totalRotY.toFixed(2)}deg) rotateZ(-1.2deg)`;
    }
  };

  useEffect(() => {
    const tick = () => { renderLoop(); frameId.current = requestAnimationFrame(tick); };
    frameId.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frameId.current);
  }, [metrics, speed, tilt]);

  const thicknessLayers = [-1.47, -0.73, 0, 0.73, 1.47];
  const baseFont = Math.round(metrics.cardW / 22.5);

  return (
    <div ref={containerRef} style={{ position: "absolute", inset: 0, overflow: "hidden", display: "flex", alignItems: "center", justifyContent: "center", pointerEvents: "none", userSelect: "none" }}>
      <div style={{ position: "relative", width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", perspective: "1350px" }}>
        <div style={{ position: "absolute", width: metrics.cardW, height: metrics.cardH, transformStyle: "preserve-3d" }}>
          {REPORTS.map((r, i) => (
            <div key={r.id} ref={(el) => { cardsRefs.current[i] = el; }}
              style={{ position: "absolute", inset: 0, width: metrics.cardW, height: metrics.cardH, transformStyle: "preserve-3d", fontFamily: "var(--font-body)", fontSize: baseFont }}>
              {thicknessLayers.map((zOffset, layerIdx) => {
                const isFrontFace = layerIdx === thicknessLayers.length - 1;
                const isBackFace = layerIdx === 0;
                if (!isFrontFace && !isBackFace) {
                  return <div key={layerIdx} style={{ position: "absolute", inset: 0, borderRadius: 8, background: "var(--rule)", border: "1px solid var(--rule)", transform: `translateZ(${zOffset}px)` }} />;
                }
                if (isFrontFace) {
                  return (
                    <div key={layerIdx} style={{ position: "absolute", inset: 0, borderRadius: 8, background: "var(--surface)", backgroundImage: "var(--tex-paper)", border: "1px solid var(--rule)", boxShadow: "var(--shadow-sticker)", overflow: "hidden", transform: `translateZ(${zOffset}px)`, backfaceVisibility: "hidden" }}>
                      <CardFront r={r} />
                    </div>
                  );
                }
                return (
                  <div key={layerIdx} style={{ position: "absolute", inset: 0, borderRadius: 8, background: "var(--paper-2)", backgroundImage: "var(--tex-note)", border: "1px solid var(--rule)", overflow: "hidden", transform: `translateZ(${zOffset}px) rotateX(180deg)`, backfaceVisibility: "hidden" }}>
                    <CardBack r={r} />
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

module.exports = { FlintCarousel };
