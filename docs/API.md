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

## `GET /api/ask?q=<question>`
Gemini with three MongoDB tools (`find_place`, `search_cases`, `area_stats`). Returns `{ answer, steps: [{ tool, args, query, ms, results }], cited: [case ids], model }`. Case files are cited in the answer as `[case:<id>]`.

## `GET /api/live?after=<ISO time>`
Long-poll over a Change Stream on `alerts`. Returns `{ alerts: [{ case_id, address, distance_m, event, processed_by, at }], via }` — immediately if alerts newer than `after` exist, otherwise after the next insert or ~20 s.

## `GET /api/demo-closure?preset=pitfield|rivington&key=<DEMO_KEY>`
Stage demo: inserts a closure event into `closure_events`. With `STREAM_PROCESSING=on` the Atlas stream processor writes the alerts; otherwise the function computes them and labels them `api-fallback`.
