/** NEXOVA brand mark (four quarter-circle leaves) with optional wordmark. */
export interface LogoProps {
  /** Mark size in px. Default 32 */
  size?: number;
  /** Show the "NEXOVA" wordmark next to the mark. Default true */
  wordmark?: boolean;
  /** Fill color. Default currentColor (white on brand surfaces) */
  color?: string;
  className?: string;
  style?: React.CSSProperties;
}
export declare function Logo(props: LogoProps): JSX.Element;
