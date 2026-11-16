# Link-preview card

The image that shows when a link to the shop is shared (Open Graph / Twitter card, 1200 × 630).
It is drawn as HTML here and rendered to PNG:

- `scamazon.html` + `card.css` → `backend/static/og-scamazon.png`

Change the HTML or `card.css`, then run `node tools/social-cards/render.mjs` with Playwright
installed (or `PLAYWRIGHT=<path to another project's node_modules/playwright>`). The tags that
point to the card are in `backend/templates/_social.html`, which `base.html` and `landing.html`
include.
