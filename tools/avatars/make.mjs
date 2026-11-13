// Draws the avatars a customer picks from at sign-up into backend/static/avatars/.
// Plain SVG, no dependencies: node tools/avatars/make.mjs
// Each is a robot with the shop's orange smile; colours, eyes and antennas vary.
import { writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const out = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', '..', 'backend', 'static', 'avatars');

const EYE = '#0f172a';

// [background, head, eyes, antenna, smile]; the smile is dark on the warm heads, where orange would not show
const robots = [
  ['#1e293b', '#38bdf8', 'round', 'ball'],
  ['#312e81', '#a78bfa', 'square', 'two'],
  ['#14532d', '#4ade80', 'visor', 'ball'],
  ['#7c2d12', '#fdba74', 'cyclops', 'none', EYE],
  ['#831843', '#f472b6', 'round', 'two'],
  ['#134e4a', '#2dd4bf', 'square', 'none'],
  ['#3f3f46', '#e4e4e7', 'cyclops', 'ball'],
  ['#713f12', '#facc15', 'visor', 'two', EYE],
];

const eyes = {
  round: `<circle cx="24" cy="31" r="4.5" fill="${EYE}"/><circle cx="40" cy="31" r="4.5" fill="${EYE}"/>`,
  square: `<rect x="19" y="26.5" width="9" height="9" rx="2" fill="${EYE}"/><rect x="36" y="26.5" width="9" height="9" rx="2" fill="${EYE}"/>`,
  visor: `<rect x="17" y="26" width="30" height="10" rx="5" fill="${EYE}"/><circle cx="25" cy="31" r="2.5" fill="#fff"/><circle cx="39" cy="31" r="2.5" fill="#fff"/>`,
  cyclops: `<circle cx="32" cy="31" r="7" fill="${EYE}"/><circle cx="34" cy="29" r="2.2" fill="#fff"/>`,
};
const antennas = {
  ball: (c) => `<path d="M32 16V9" stroke="${c}" stroke-width="3" stroke-linecap="round"/><circle cx="32" cy="8" r="3.5" fill="#ff9900"/>`,
  two: (c) => `<path d="M24 17l-4-8M40 17l4-8" stroke="${c}" stroke-width="3" stroke-linecap="round"/><circle cx="19.5" cy="8" r="3" fill="#ff9900"/><circle cx="44.5" cy="8" r="3" fill="#ff9900"/>`,
  none: () => '',
};

robots.forEach(([bg, head, eye, antenna, smile = '#ff9900'], i) => {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="14" fill="${bg}"/>
  ${antennas[antenna](head)}
  <rect x="12" y="16" width="40" height="36" rx="10" fill="${head}"/>
  <rect x="7" y="28" width="5" height="12" rx="2.5" fill="${head}"/>
  <rect x="52" y="28" width="5" height="12" rx="2.5" fill="${head}"/>
  ${eyes[eye]}
  <path d="M22 41 Q32 49 42 41" fill="none" stroke="${smile}" stroke-width="3.5" stroke-linecap="round"/>
  <path d="M38.5 39.5l4 1.2-1 4" fill="none" stroke="${smile}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
`;
  writeFileSync(path.join(out, `avatar-${i + 1}.svg`), svg);
});
console.log(`${robots.length} avatars in ${out}`);
