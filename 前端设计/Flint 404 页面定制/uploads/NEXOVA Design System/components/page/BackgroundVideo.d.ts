/** Full-bleed looping background video (Earth-from-space by default), absolute behind content. */
export interface BackgroundVideoProps {
  /** Video URL. Defaults to the NEXOVA Earth-from-space loop */
  src?: string;
  poster?: string;
}
export declare function BackgroundVideo(props: BackgroundVideoProps): JSX.Element;
