# Tell Me WHY

**Before you sign the lease, find out who failed here before you. Before you take the shift, check who you'd really be working for.**

Encode London Hackathon 2026 · track *The Real World* · built on MongoDB Atlas + Gemini (`gemini-4-argon`).

## What it does
- **Owner mode:** an investigation board for one London neighbourhood (around Encode Hub). Every closure at an address is a case file: the chain of companies that traded there, how long each lasted, whether the closure is confirmed, and 2–3 hypotheses for *why*, each with evidence, confidence and a counter-argument.
- **Worker mode:** enter a venue name, get a traffic-light employer check: the company behind the venue was dissolved while the venue keeps trading, fast company turnover at the address, new company registered right after the old one closed. Plus questions to ask and where to get help (Acas, HMRC, Redundancy Payments Service).

## Facts first, model second
- Facts are computed from data: Companies House (dissolved food companies, SIC 56xxx), FSA Food Hygiene, Google Places, TfL, ONS Census 2021.
- **Every closure is double-checked.** Restaurants often change the company behind them, so a dissolved company is not treated as a closure until we check Google Places and FSA for a venue with the same name still trading (`scripts/verify_closures.py`). Verdicts: `closed_google`, `operating_now` (company changed, venue open), `no_trace`, `unclear`.
- Gemini only phrases hypotheses over those facts (`scripts/gen_reasons.py`), with structured JSON output.

## MongoDB Atlas
Database `deadspot`: `places` (FSA), `google`, `companies`, `stations`, `areas`, `cases`.
- 2dsphere indexes on `location` (geo queries around an address)
- Atlas Search on Google reviews (`google_text`)
- Vector Search with Automated Embedding (Voyage) on case analyses (`cases_autoembed`)

## Run locally
```
npm run dev   # http://localhost:3000
```
The app runs from a snapshot in `app/data/` so the demo does not depend on network calls. API: `/api/cases`, `/api/case?id=…`, `/api/employer-check?q=…`.

## Data pipeline
`scripts/collect_*.py` → `scripts/load_atlas.py` → `scripts/build_cases.py` → `scripts/verify_closures.py` → `scripts/gen_reasons.py` → `scripts/make_indexes.py`, `scripts/make_vector.py`.
Secrets live in local files that are git-ignored (`*_key.txt`, `atlas_password.txt`).

## Honest limits
Closure reasons are hypotheses, not facts. Companies House addresses are registered offices and may differ from trading addresses. Coverage is ~400 m around Encode Hub.
