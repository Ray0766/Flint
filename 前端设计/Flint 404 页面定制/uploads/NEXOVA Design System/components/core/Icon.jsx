import React from 'react';
const P = React.createElement;
const PATHS = {
  'arrow-right': [['path',{d:'M5 12h14'}],['path',{d:'m12 5 7 7-7 7'}]],
  'menu': [['line',{x1:4,x2:20,y1:12,y2:12}],['line',{x1:4,x2:20,y1:6,y2:6}],['line',{x1:4,x2:20,y1:18,y2:18}]],
  'x': [['path',{d:'M18 6 6 18'}],['path',{d:'m6 6 12 12'}]],
  'facebook': [['path',{d:'M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z'}]],
  'twitter': [['path',{d:'M22 4s-.7 2.1-2 3.4c1.6 10-9.4 17.3-18 11.6 2.2.1 4.4-.6 6-2C3 15.5.5 9.6 3 5c2.2 2.6 5.6 4.1 9 4-.9-4.2 4-6.6 7-3.8 1.1 0 3-1.2 3-1.2z'}]],
  'dribbble': [['circle',{cx:12,cy:12,r:10}],['path',{d:'M19.13 5.09C15.22 9.14 10 10.44 2.25 10.94'}],['path',{d:'M21.75 12.84c-6.62-1.41-12.14 1-16.38 6.32'}],['path',{d:'M8.56 2.75c4.37 6 6 9.42 8 17.72'}]],
  'youtube': [['path',{d:'M2.5 17a24.12 24.12 0 0 1 0-10 2 2 0 0 1 1.4-1.4 49.56 49.56 0 0 1 16.2 0A2 2 0 0 1 21.5 7a24.12 24.12 0 0 1 0 10 2 2 0 0 1-1.4 1.4 49.55 49.55 0 0 1-16.2 0A2 2 0 0 1 2.5 17'}],['path',{d:'m10 15 5-3-5-3z'}]],
  'linkedin': [['path',{d:'M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4V8h4'}],['rect',{width:4,height:12,x:2,y:9}],['circle',{cx:4,cy:4,r:2}]],
  'instagram': [['rect',{width:20,height:20,x:2,y:2,rx:5,ry:5}],['path',{d:'M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z'}],['line',{x1:17.5,x2:17.51,y1:6.5,y2:6.5}]]
};
export function Icon({ name, size = 16, strokeWidth = 2, className = '', style }) {
  const parts = PATHS[name] || [];
  return P('svg', { width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth, strokeLinecap: 'round', strokeLinejoin: 'round', className, style, 'aria-hidden': true },
    parts.map((p, i) => P(p[0], { key: i, ...p[1] })));
}
