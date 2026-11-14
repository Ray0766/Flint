/** Centered error hero: two light subtitle lines, giant glowing code, liquid-glass CTA. */
export interface Hero404Props {
  /** First subtitle line. Default 'This page seems to have' */
  line1?: string;
  /** Second subtitle line. Default 'slipped beyond our reach :/' */
  line2?: string;
  /** Giant display text. Default '404' */
  code?: string;
  /** CTA label. Default 'Return to Main Page' */
  ctaLabel?: string;
  ctaHref?: string;
}
export declare function Hero404(props: Hero404Props): JSX.Element;
