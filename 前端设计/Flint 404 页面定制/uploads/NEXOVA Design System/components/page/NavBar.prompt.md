Full site nav: logo left, links center (desktop only), gradient LOG IN right, hamburger + blur-panel stagger menu below the lg breakpoint. Place inside a `position:relative` page root (the mobile panel anchors to it at top 68px).

```jsx
<NavBar onLogin={() => {}} />
<NavBar links={['Domain','Servers','Cloud']} loginLabel="SIGN UP" />
```
