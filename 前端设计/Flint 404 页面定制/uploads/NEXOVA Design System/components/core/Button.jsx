import React from 'react';
export function Button({ variant = 'gradient', href, onClick, type = 'button', className = '', style, children }) {
  const cls = 'nx-btn ' + (variant === 'glass' ? 'liquid-glass nx-btn--glass' : 'nx-btn--gradient') + (className ? ' ' + className : '');
  if (href != null) return <a href={href} className={cls} style={style} onClick={onClick}>{children}</a>;
  return <button type={type} className={cls} style={style} onClick={onClick}>{children}</button>;
}
