/** NEXOVA multi-column footer: 4 link columns + newsletter signup + social icon row. */
export interface FooterProps {
  /** Link columns. Default: SERVERS / DOMAINS / HELP US / ABOUT */
  columns?: { title: string; links: string[] }[];
  /** Newsletter heading. Default 'JOIN FOR EXCLUSIVE DEALS' */
  newsletterTitle?: string;
  /** Submit label. Default 'SEND IT' */
  sendLabel?: string;
  /** Input placeholder. Default 'Type your email to sign up' */
  placeholder?: string;
  /** Social heading. Default 'CONNECT' */
  connectTitle?: string;
  /** Icon names for the social row. Default facebook…instagram */
  socials?: string[];
}
export declare function Footer(props: FooterProps): JSX.Element;
