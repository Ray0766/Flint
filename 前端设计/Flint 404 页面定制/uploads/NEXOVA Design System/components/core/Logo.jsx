import React from 'react';
export function Logo({ size = 32, wordmark = true, color = 'currentColor', className = '', style }) {
  return (
    <span className={'nx-logo ' + className} style={style}>
      <svg width={size} height={size} viewBox="0 0 480 480" fill={color} aria-hidden="true">
        <path d="M480 240a240 240 0 0 0-240 240 240 240 0 0 0 240-240Z"></path>
        <path d="M240 0A240 240 0 0 0 0 240 240 240 0 0 0 240 0Z"></path>
        <path d="M480 240A240 240 0 0 0 240 0a240 240 0 0 0 240 240Z"></path>
        <path d="M240 480A240 240 0 0 0 0 240a240 240 0 0 0 240 240Z"></path>
      </svg>
      {wordmark && <span className="nx-logo-text">NEXOVA</span>}
    </span>
  );
}
