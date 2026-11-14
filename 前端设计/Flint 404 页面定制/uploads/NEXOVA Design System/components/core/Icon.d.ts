/** Lucide-style stroke icon (inlined copies of the glyphs NEXOVA uses). */
export interface IconProps {
  /** One of: arrow-right, menu, x, facebook, twitter, dribbble, youtube, linkedin, instagram */
  name: string;
  /** Square size in px. Default 16 */
  size?: number;
  strokeWidth?: number;
  className?: string;
  style?: React.CSSProperties;
}
export declare function Icon(props: IconProps): JSX.Element;
