# Tell Me WHY — design handoff

Ready for Claude to integrate. Everything authored for this handoff lives in `design/`; the existing `app/`, API work and source data were not edited.

## Open the prototype

From the hackathon project folder:

```sh
python3 design/serve.py
```

Open http://127.0.0.1:8765/design/ . The preview server exposes only the design files and `app/data/cases.json`, not the project root or its credentials. Open `review.html` for a scaled desktop overview. Stop with Ctrl+C. Opening the HTML directly with `file://` cannot load its JSON.

## Five screens

| File | Purpose | Working interactions |
| --- | --- | --- |
| `index.html` | Home / two user modes | Mode switch; address or venue search; three example streets |
| `board.html` | Owner board | Leaflet map; 61 address cases; five evidence filters; live search; linked pins and cards; empty state |
| `case.html?id=…` | Full address case | Company timeline; verdicts; current listings; local context; hypotheses and counterarguments; expandable sources |
| `employer.html?q=…` | Employer check | Search across address, company and venue names; ambiguous-match selection; signal cards; local checklist; official support links |
| `share.html?id=…` | Share / QR | Editable URL; valid QR generation; copy link; SVG download; print card |

Default detailed case: `14-rivington-st-EC2A3DU`.

## Visual direction

Warm ivory paper, dark ink, terracotta closures, muted green trading signals, ochre uncertainty. Quiet sans-serif typography and a real map rather than a generated illustration. Julia's explicit preference for light colours and simple lettering takes precedence over the earlier dark-theme proposal in `vision-and-plan.md`. No generated headline lettering or decorative stock artwork.

`tokens.css` contains colour, typography, spacing, radius and shadow variables. `styles.css` contains shared components and responsive layouts (700px and 1000px breakpoints). At narrow widths map and list stack; the full case becomes one column. Colour is always paired with text.

## Integration

Read `COMPONENTS.md` for component and field mappings. Pages are buildless HTML/CSS and shared vanilla JS, with no framework or package installation. Page-specific markup is rendered by named functions in `app.js`; carry those functions or their HTML templates into the app as needed.

The loader uses `../app/data/cases.json`, a read-only input. `assets/sample-case.json` is an unchanged snapshot of `build/sample_case.json` for fallback if the full dataset cannot be loaded. The fallback is announced. API integration is intentionally left to Claude: replace the loader with `/api/cases` and `/api/case/:id` while retaining the field names. No API requests, Atlas credentials or Gemini calls are implemented here.

### Analysis language

The supplied model analysis is in Russian. `assets/sample-analysis.en.json` is a manually translated English presentation of the sample case's `analysis.headline`, `hypotheses` (including evidence, confidence and counterargument) and `caveat`. No API schema was changed. It is a presentation fixture, not a fresh model result. Other cases deliberately show an English “analysis not supplied” state instead of inventing explanations. Replace `analysisFor(c)` with the API's English `analysis` when available. Original verification notes remain verbatim in the expandable sources section, labelled as supplied-language text.

### Evidence semantics — preserve these during integration

- `closure_level=confirmed` renders as **Closure evidence found**, not “permanently closed.” Chingu's own note says `CLOSED_TEMPORARILY`. The timeline renders it as **Temporarily closed · Google**.
- `chain.opened`, `closed` and `months` are labelled **company records / company lifespan**, not verified restaurant trading dates.
- `now_here` is labelled **Listed at this address**. These records may overlap and do not establish the present tenant.
- No source-collection timestamps exist in the case payload. The UI says **Check date not supplied**, never invents a freshness date. FSA `rating_date` is shown as a rating date only.
- Links to Companies House are built only from actual `company_number`; Google place links use actual verification evidence IDs. Source chips without record identifiers are labels, not invented record links.
- Hypotheses keep confidence and counterarguments together. Model confidence is not a calibrated probability.
- The worker screen uses existing case records only and stays **amber / needs verification**. It does not infer employer insolvency, job security or director continuity from a closed company at an address. Gazette, directors and payroll are visibly **Not checked**. Replace with a documented `/api/employer-check` response when that exists; do not invent red/green assessments.
- The share page generates a real QR locally. Localhost links are identified as local preview; replace with the deployed case URL for phone use. The URL's reachability is not verified by the generator.

## Components and accessibility

Native links/buttons/forms, labelled inputs, visible focus rings, skip link, `aria-pressed` filters, live result counts, reduced-motion styling, accessible marker names, native disclosure and checkboxes. JSON strings are HTML-escaped before rendering. No analytics, submissions, payments or persistence. Checklists reset on reload.

## Dependencies and network

Vendored Leaflet 1.9.4 and qrcode-generator 1.4.4 in `vendor/`. No CDN scripts or remote font dependency. Map tiles come from OpenStreetMap with attribution and require network access. When unavailable, show a notice; geolocated pins and the address list still work. This is not a fully offline street map.

Official assistance links: Acas insolvency page, GOV.UK Redundancy Payments Service, HMRC personal tax account, Citizens Advice employer closure guidance. Links are a route to current guidance; the prototype does not calculate legal entitlements.

## Validation

- JavaScript syntax checked with Node.
- Browser: all five screens opened, mobile layout inspected at 528px and wider layout at 897px; desktop 1440px composition inspected via `review.html`.
- Board shows 61 cases; closure-evidence filter shows 3; search and no-results state verified.
- Rivington case opens; Chingu temporary closure remains distinct from permanent closure.
- Employer no-match state verified.
- QR invalid URL disables saving; valid URL restores QR generation.
- No backend integration or production deployment was performed. Phone QR scanning and an actual printed card have not been tested.
