/* @ds-bundle: {"format":4,"namespace":"NEXOVADesignSystem_7abf1c","components":[{"name":"Button","sourcePath":"components/core/Button.jsx"},{"name":"Icon","sourcePath":"components/core/Icon.jsx"},{"name":"Logo","sourcePath":"components/core/Logo.jsx"},{"name":"BackgroundVideo","sourcePath":"components/page/BackgroundVideo.jsx"},{"name":"Footer","sourcePath":"components/page/Footer.jsx"},{"name":"Hero404","sourcePath":"components/page/Hero404.jsx"},{"name":"NavBar","sourcePath":"components/page/NavBar.jsx"}],"sourceHashes":{"components/core/Button.jsx":"d488e82e76fb","components/core/Icon.jsx":"69930b737e3b","components/core/Logo.jsx":"293f5c169d20","components/page/BackgroundVideo.jsx":"b8ddf47e3414","components/page/Footer.jsx":"112f6365c895","components/page/Hero404.jsx":"b25086f0b0a5","components/page/NavBar.jsx":"716b6823e682"},"inlinedExternals":[],"unexposedExports":[]} */

(() => {

const __ds_ns = (window.NEXOVADesignSystem_7abf1c = window.NEXOVADesignSystem_7abf1c || {});

const __ds_scope = {};

(__ds_ns.__errors = __ds_ns.__errors || []);

// components/core/Button.jsx
try { (() => {
function Button({
  variant = 'gradient',
  href,
  onClick,
  type = 'button',
  className = '',
  style,
  children
}) {
  const cls = 'nx-btn ' + (variant === 'glass' ? 'liquid-glass nx-btn--glass' : 'nx-btn--gradient') + (className ? ' ' + className : '');
  if (href != null) return /*#__PURE__*/React.createElement("a", {
    href: href,
    className: cls,
    style: style,
    onClick: onClick
  }, children);
  return /*#__PURE__*/React.createElement("button", {
    type: type,
    className: cls,
    style: style,
    onClick: onClick
  }, children);
}
Object.assign(__ds_scope, { Button });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Button.jsx", error: String((e && e.message) || e) }); }

// components/core/Icon.jsx
try { (() => {
const P = React.createElement;
const PATHS = {
  'arrow-right': [['path', {
    d: 'M5 12h14'
  }], ['path', {
    d: 'm12 5 7 7-7 7'
  }]],
  'menu': [['line', {
    x1: 4,
    x2: 20,
    y1: 12,
    y2: 12
  }], ['line', {
    x1: 4,
    x2: 20,
    y1: 6,
    y2: 6
  }], ['line', {
    x1: 4,
    x2: 20,
    y1: 18,
    y2: 18
  }]],
  'x': [['path', {
    d: 'M18 6 6 18'
  }], ['path', {
    d: 'm6 6 12 12'
  }]],
  'facebook': [['path', {
    d: 'M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z'
  }]],
  'twitter': [['path', {
    d: 'M22 4s-.7 2.1-2 3.4c1.6 10-9.4 17.3-18 11.6 2.2.1 4.4-.6 6-2C3 15.5.5 9.6 3 5c2.2 2.6 5.6 4.1 9 4-.9-4.2 4-6.6 7-3.8 1.1 0 3-1.2 3-1.2z'
  }]],
  'dribbble': [['circle', {
    cx: 12,
    cy: 12,
    r: 10
  }], ['path', {
    d: 'M19.13 5.09C15.22 9.14 10 10.44 2.25 10.94'
  }], ['path', {
    d: 'M21.75 12.84c-6.62-1.41-12.14 1-16.38 6.32'
  }], ['path', {
    d: 'M8.56 2.75c4.37 6 6 9.42 8 17.72'
  }]],
  'youtube': [['path', {
    d: 'M2.5 17a24.12 24.12 0 0 1 0-10 2 2 0 0 1 1.4-1.4 49.56 49.56 0 0 1 16.2 0A2 2 0 0 1 21.5 7a24.12 24.12 0 0 1 0 10 2 2 0 0 1-1.4 1.4 49.55 49.55 0 0 1-16.2 0A2 2 0 0 1 2.5 17'
  }], ['path', {
    d: 'm10 15 5-3-5-3z'
  }]],
  'linkedin': [['path', {
    d: 'M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4V8h4'
  }], ['rect', {
    width: 4,
    height: 12,
    x: 2,
    y: 9
  }], ['circle', {
    cx: 4,
    cy: 4,
    r: 2
  }]],
  'instagram': [['rect', {
    width: 20,
    height: 20,
    x: 2,
    y: 2,
    rx: 5,
    ry: 5
  }], ['path', {
    d: 'M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z'
  }], ['line', {
    x1: 17.5,
    x2: 17.51,
    y1: 6.5,
    y2: 6.5
  }]]
};
function Icon({
  name,
  size = 16,
  strokeWidth = 2,
  className = '',
  style
}) {
  const parts = PATHS[name] || [];
  return P('svg', {
    width: size,
    height: size,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
    className,
    style,
    'aria-hidden': true
  }, parts.map((p, i) => P(p[0], {
    key: i,
    ...p[1]
  })));
}
Object.assign(__ds_scope, { Icon });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Icon.jsx", error: String((e && e.message) || e) }); }

// components/core/Logo.jsx
try { (() => {
function Logo({
  size = 32,
  wordmark = true,
  color = 'currentColor',
  className = '',
  style
}) {
  return /*#__PURE__*/React.createElement("span", {
    className: 'nx-logo ' + className,
    style: style
  }, /*#__PURE__*/React.createElement("svg", {
    width: size,
    height: size,
    viewBox: "0 0 480 480",
    fill: color,
    "aria-hidden": "true"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M480 240a240 240 0 0 0-240 240 240 240 0 0 0 240-240Z"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M240 0A240 240 0 0 0 0 240 240 240 0 0 0 240 0Z"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M480 240A240 240 0 0 0 240 0a240 240 0 0 0 240 240Z"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M240 480A240 240 0 0 0 0 240a240 240 0 0 0 240 240Z"
  })), wordmark && /*#__PURE__*/React.createElement("span", {
    className: "nx-logo-text"
  }, "NEXOVA"));
}
Object.assign(__ds_scope, { Logo });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Logo.jsx", error: String((e && e.message) || e) }); }

// components/page/BackgroundVideo.jsx
try { (() => {
const DEFAULT_SRC = 'https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260613_180732_a54afbf6-b30d-470e-861f-669871f09f67.mp4';
function BackgroundVideo({
  src = DEFAULT_SRC,
  poster
}) {
  return /*#__PURE__*/React.createElement("video", {
    className: "nx-video",
    src: src,
    poster: poster,
    autoPlay: true,
    muted: true,
    loop: true,
    playsInline: true
  });
}
Object.assign(__ds_scope, { BackgroundVideo });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/page/BackgroundVideo.jsx", error: String((e && e.message) || e) }); }

// components/page/Footer.jsx
try { (() => {
const COLUMNS = [{
  title: 'SERVERS',
  links: ['Web Servers', 'VPS Servers', 'Cloud Servers', 'Managed Instances', 'Bare Metal']
}, {
  title: 'DOMAINS',
  links: ['Find Domain', 'Move Domains', 'DNS Manager', 'Domain Costs']
}, {
  title: 'HELP US',
  links: ['Open a Ticket', 'FAQs', 'Docs', 'Tutorials', 'Forum']
}, {
  title: 'ABOUT',
  links: ['Our Story', 'Leadership Team', 'Press Room', 'We Hire', 'Alliance', 'Blog']
}];
const SOCIALS = ['facebook', 'twitter', 'dribbble', 'youtube', 'linkedin', 'instagram'];
function Footer({
  columns = COLUMNS,
  newsletterTitle = 'JOIN FOR EXCLUSIVE DEALS',
  sendLabel = 'SEND IT',
  placeholder = 'Type your email to sign up',
  connectTitle = 'CONNECT',
  socials = SOCIALS
}) {
  return /*#__PURE__*/React.createElement("footer", {
    className: "nx-footer"
  }, /*#__PURE__*/React.createElement("div", {
    className: "nx-footer-grid"
  }, columns.map(col => /*#__PURE__*/React.createElement("div", {
    key: col.title
  }, /*#__PURE__*/React.createElement("h3", {
    className: "nx-footer-title"
  }, col.title), /*#__PURE__*/React.createElement("ul", {
    className: "nx-footer-list"
  }, col.links.map(l => /*#__PURE__*/React.createElement("li", {
    key: l
  }, /*#__PURE__*/React.createElement("a", {
    className: "nx-footer-link",
    href: "#"
  }, l)))))), /*#__PURE__*/React.createElement("div", {
    className: "nx-footer-news"
  }, /*#__PURE__*/React.createElement("h3", {
    className: "nx-footer-title"
  }, newsletterTitle), /*#__PURE__*/React.createElement("form", {
    className: "nx-news-form",
    onSubmit: e => e.preventDefault()
  }, /*#__PURE__*/React.createElement("input", {
    className: "nx-news-input",
    type: "email",
    placeholder: placeholder
  }), /*#__PURE__*/React.createElement("button", {
    className: "nx-news-btn",
    type: "submit"
  }, sendLabel)), /*#__PURE__*/React.createElement("h3", {
    className: "nx-footer-title nx-connect"
  }, connectTitle), /*#__PURE__*/React.createElement("div", {
    className: "nx-social"
  }, socials.map(s => /*#__PURE__*/React.createElement("a", {
    key: s,
    href: "#",
    "aria-label": s
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: s,
    size: 16
  })))))));
}
Object.assign(__ds_scope, { Footer });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/page/Footer.jsx", error: String((e && e.message) || e) }); }

// components/page/Hero404.jsx
try { (() => {
function Hero404({
  line1 = 'This page seems to have',
  line2 = 'slipped beyond our reach :/',
  code = '404',
  ctaLabel = 'Return to Main Page',
  ctaHref = '#'
}) {
  return /*#__PURE__*/React.createElement("main", {
    className: "nx-hero"
  }, /*#__PURE__*/React.createElement("h1", {
    className: "nx-hero-line"
  }, line1), /*#__PURE__*/React.createElement("h1", {
    className: "nx-hero-line"
  }, line2), /*#__PURE__*/React.createElement("div", {
    className: "nx-hero-404-wrap"
  }, /*#__PURE__*/React.createElement("span", {
    className: "four-oh-four"
  }, code)), /*#__PURE__*/React.createElement("a", {
    href: ctaHref,
    className: "nx-btn liquid-glass nx-btn--glass"
  }, ctaLabel));
}
Object.assign(__ds_scope, { Hero404 });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/page/Hero404.jsx", error: String((e && e.message) || e) }); }

// components/page/NavBar.jsx
try { (() => {
const DEFAULT_LINKS = ['Domain', 'Servers', 'Cloud', 'Managed', 'Email', 'Privacy'];
function NavBar({
  links = DEFAULT_LINKS,
  loginLabel = 'LOG IN',
  onLogin
}) {
  const [open, setOpen] = React.useState(false);
  const [visible, setVisible] = React.useState(false);
  const closeTimer = React.useRef(null);
  React.useEffect(() => {
    if (open) {
      const id = setTimeout(() => setVisible(true), 20);
      return () => clearTimeout(id);
    }
  }, [open]);
  React.useEffect(() => () => clearTimeout(closeTimer.current), []);
  const close = () => {
    setVisible(false);
    closeTimer.current = setTimeout(() => setOpen(false), 500);
  };
  const toggle = () => {
    if (open && visible) close();else {
      clearTimeout(closeTimer.current);
      setOpen(true);
    }
  };
  return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("nav", {
    className: "nx-nav"
  }, /*#__PURE__*/React.createElement("a", {
    href: "#",
    className: "nx-logo",
    style: {
      gap: 10
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.Logo, {
    size: 32,
    wordmark: true
  })), /*#__PURE__*/React.createElement("div", {
    className: "nx-nav-links"
  }, links.map(l => /*#__PURE__*/React.createElement("a", {
    key: l,
    className: "nx-nav-link",
    href: "#"
  }, l))), /*#__PURE__*/React.createElement(__ds_scope.Button, {
    className: "nx-nav-login",
    onClick: onLogin
  }, loginLabel, " ", /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "arrow-right",
    size: 16
  })), /*#__PURE__*/React.createElement("button", {
    className: "nx-burger",
    "aria-label": "Toggle menu",
    onClick: toggle
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "menu",
    size: 24,
    className: visible ? 'is-hidden-neg' : 'is-active'
  }), /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "x",
    size: 24,
    className: visible ? 'is-active' : 'is-hidden'
  }))), open && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
    className: 'nx-menu-backdrop' + (visible ? ' is-open' : ''),
    onClick: close
  }), /*#__PURE__*/React.createElement("div", {
    className: "nx-menu"
  }, /*#__PURE__*/React.createElement("div", {
    className: "nx-menu-blur"
  }), /*#__PURE__*/React.createElement("div", {
    className: "nx-menu-content"
  }, links.map((l, i) => /*#__PURE__*/React.createElement("a", {
    key: l,
    href: "#",
    className: 'nx-menu-item' + (visible ? ' is-in' : ''),
    style: {
      transitionDelay: visible ? 350 + i * 50 + 'ms' : '0ms'
    },
    onClick: close
  }, l)), /*#__PURE__*/React.createElement(__ds_scope.Button, {
    className: 'nx-menu-item' + (visible ? ' is-in' : ''),
    style: {
      transitionDelay: visible ? 350 + links.length * 50 + 'ms' : '0ms'
    },
    onClick: close
  }, loginLabel, " ", /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "arrow-right",
    size: 16
  }))))));
}
Object.assign(__ds_scope, { NavBar });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/page/NavBar.jsx", error: String((e && e.message) || e) }); }

__ds_ns.Button = __ds_scope.Button;

__ds_ns.Icon = __ds_scope.Icon;

__ds_ns.Logo = __ds_scope.Logo;

__ds_ns.BackgroundVideo = __ds_scope.BackgroundVideo;

__ds_ns.Footer = __ds_scope.Footer;

__ds_ns.Hero404 = __ds_scope.Hero404;

__ds_ns.NavBar = __ds_scope.NavBar;

})();
