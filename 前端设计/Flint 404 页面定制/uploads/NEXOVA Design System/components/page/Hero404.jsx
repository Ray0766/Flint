import React from 'react';
export function Hero404({ line1 = 'This page seems to have', line2 = 'slipped beyond our reach :/', code = '404', ctaLabel = 'Return to Main Page', ctaHref = '#' }) {
  return (
    <main className="nx-hero">
      <h1 className="nx-hero-line">{line1}</h1>
      <h1 className="nx-hero-line">{line2}</h1>
      <div className="nx-hero-404-wrap"><span className="four-oh-four">{code}</span></div>
      <a href={ctaHref} className="nx-btn liquid-glass nx-btn--glass">{ctaLabel}</a>
    </main>
  );
}
