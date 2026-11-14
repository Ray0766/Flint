/** NEXOVA top navigation: logo, center links (≥lg), gradient LOG IN, animated mobile menu below lg. */
export interface NavBarProps {
  /** Nav link labels. Default: Domain, Servers, Cloud, Managed, Email, Privacy */
  links?: string[];
  /** Login button label. Default 'LOG IN' */
  loginLabel?: string;
  onLogin?: (e: React.MouseEvent) => void;
}
export declare function NavBar(props: NavBarProps): JSX.Element;
