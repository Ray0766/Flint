import React from 'react';
import { Logo } from '../core/Logo.jsx';
import { Button } from '../core/Button.jsx';
import { Icon } from '../core/Icon.jsx';
const DEFAULT_LINKS = ['Domain', 'Servers', 'Cloud', 'Managed', 'Email', 'Privacy'];
export function NavBar({ links = DEFAULT_LINKS, loginLabel = 'LOG IN', onLogin }) {
  const [open, setOpen] = React.useState(false);
  const [visible, setVisible] = React.useState(false);
  const closeTimer = React.useRef(null);
  React.useEffect(() => {
    if (open) { const id = setTimeout(() => setVisible(true), 20); return () => clearTimeout(id); }
  }, [open]);
  React.useEffect(() => () => clearTimeout(closeTimer.current), []);
  const close = () => { setVisible(false); closeTimer.current = setTimeout(() => setOpen(false), 500); };
  const toggle = () => { if (open && visible) close(); else { clearTimeout(closeTimer.current); setOpen(true); } };
  return (
    <React.Fragment>
      <nav className="nx-nav">
        <a href="#" className="nx-logo" style={{ gap: 10 }}><Logo size={32} wordmark={true} /></a>
        <div className="nx-nav-links">{links.map((l) => <a key={l} className="nx-nav-link" href="#">{l}</a>)}</div>
        <Button className="nx-nav-login" onClick={onLogin}>{loginLabel} <Icon name="arrow-right" size={16} /></Button>
        <button className="nx-burger" aria-label="Toggle menu" onClick={toggle}>
          <Icon name="menu" size={24} className={visible ? 'is-hidden-neg' : 'is-active'} />
          <Icon name="x" size={24} className={visible ? 'is-active' : 'is-hidden'} />
        </button>
      </nav>
      {open && (
        <React.Fragment>
          <div className={'nx-menu-backdrop' + (visible ? ' is-open' : '')} onClick={close}></div>
          <div className="nx-menu">
            <div className="nx-menu-blur"></div>
            <div className="nx-menu-content">
              {links.map((l, i) => (
                <a key={l} href="#" className={'nx-menu-item' + (visible ? ' is-in' : '')} style={{ transitionDelay: visible ? (350 + i * 50) + 'ms' : '0ms' }} onClick={close}>{l}</a>
              ))}
              <Button className={'nx-menu-item' + (visible ? ' is-in' : '')} style={{ transitionDelay: visible ? (350 + links.length * 50) + 'ms' : '0ms' }} onClick={close}>{loginLabel} <Icon name="arrow-right" size={16} /></Button>
            </div>
          </div>
        </React.Fragment>
      )}
    </React.Fragment>
  );
}
