import React from 'react';
import { Icon } from '../core/Icon.jsx';
const COLUMNS = [
  { title: 'SERVERS', links: ['Web Servers', 'VPS Servers', 'Cloud Servers', 'Managed Instances', 'Bare Metal'] },
  { title: 'DOMAINS', links: ['Find Domain', 'Move Domains', 'DNS Manager', 'Domain Costs'] },
  { title: 'HELP US', links: ['Open a Ticket', 'FAQs', 'Docs', 'Tutorials', 'Forum'] },
  { title: 'ABOUT', links: ['Our Story', 'Leadership Team', 'Press Room', 'We Hire', 'Alliance', 'Blog'] }
];
const SOCIALS = ['facebook', 'twitter', 'dribbble', 'youtube', 'linkedin', 'instagram'];
export function Footer({ columns = COLUMNS, newsletterTitle = 'JOIN FOR EXCLUSIVE DEALS', sendLabel = 'SEND IT', placeholder = 'Type your email to sign up', connectTitle = 'CONNECT', socials = SOCIALS }) {
  return (
    <footer className="nx-footer">
      <div className="nx-footer-grid">
        {columns.map((col) => (
          <div key={col.title}>
            <h3 className="nx-footer-title">{col.title}</h3>
            <ul className="nx-footer-list">{col.links.map((l) => <li key={l}><a className="nx-footer-link" href="#">{l}</a></li>)}</ul>
          </div>
        ))}
        <div className="nx-footer-news">
          <h3 className="nx-footer-title">{newsletterTitle}</h3>
          <form className="nx-news-form" onSubmit={(e) => e.preventDefault()}>
            <input className="nx-news-input" type="email" placeholder={placeholder} />
            <button className="nx-news-btn" type="submit">{sendLabel}</button>
          </form>
          <h3 className="nx-footer-title nx-connect">{connectTitle}</h3>
          <div className="nx-social">{socials.map((s) => <a key={s} href="#" aria-label={s}><Icon name={s} size={16} /></a>)}</div>
        </div>
      </div>
    </footer>
  );
}
