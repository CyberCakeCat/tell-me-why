# API contract

Same data as `app/data/cases.json`. All responses are JSON.

## `GET /api/cases[?level=confirmed|probable|possible|entity_change]`
Array of case files (fields: see `design/README.md`).

## `GET /api/case?id=<case id>`
One case file, or 404.

## `GET /api/employer-check?id=<case id>` or `?q=<venue, company or address>`
```json
{
  "verdict": "amber",              // red | amber | green | unknown
  "case_id": "57-pitfield-st-N16BU",
  "address": "57 Pitfield Street, London",
  "signals": [
    { "level": "amber", "text": "The company was dissolved but the venue is still trading (...). Needs verification: ask who your employer is on paper before your first shift.", "source": "Companies House + FSA" }
  ],
  "chain": [ /* companies at the address, same as in the case file */ ],
  "disclaimer": "Signals from public records, not an accusation or legal advice.",
  "checked_at": "2026-10-24"
}
```

**Colours (agreed 24 Oct):** `amber` = needs verification (anything inferred from company changes). `red` = only a confirmed insolvency procedure from Companies House (liquidation, administration, receivership) — not connected yet, so no venue is red today. `green` = no signals in our data, not a guarantee. `unknown` = venue not in our area.

Logic lives in `app/lib/employer.js` (works in the browser as `window.Employer` and in Node), so a page can also compute it without the API.
