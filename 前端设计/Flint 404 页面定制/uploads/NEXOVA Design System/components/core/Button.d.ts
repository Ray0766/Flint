/**
 * NEXOVA pill button: emerald→cyan gradient CTA or liquid-glass ghost.
 * @startingPoint section="Components" subtitle="Gradient CTA and liquid-glass pill buttons" viewport="700x220"
 */
export interface ButtonProps {
  /** 'gradient' (emerald→cyan CTA) | 'glass' (liquid-glass, uppercase tracked). Default 'gradient' */
  variant?: 'gradient' | 'glass';
  /** Renders an <a> instead of <button> */
  href?: string;
  onClick?: (e: React.MouseEvent) => void;
  type?: 'button' | 'submit';
  className?: string;
  style?: React.CSSProperties;
  children?: React.ReactNode;
}
export declare function Button(props: ButtonProps): JSX.Element;
