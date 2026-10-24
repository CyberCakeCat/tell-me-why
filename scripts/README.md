# Data pipeline

Run from the project root (`python3 scripts/<name>.py [area]`). Keys and the Atlas password live in git-ignored files (`*_key.txt`, `atlas_user.txt`, `atlas_password.txt`). Areas are defined in `areas.py` (`shoreditch`, `richmond`); collectors take the area as their first argument.

| Step | Script | What it does |
|---|---|---|
| 1. Collect | `collect_fsa.py`, `collect_google.py`, `collect_companies.py`, `collect_stations.py`, `collect_areas.py` | FSA hygiene register, Google Places, dissolved food companies (Companies House), TfL stations, ONS Census 2021 |
| 2. Load | `load_atlas.py` (Shoreditch, first load), `load_area.py <area>` | Raw collections into Atlas, tagged by area |
| 3. Address histories | `build_cases.py <area>` → `verify_closures.py` | Companies grouped by address; each one checked against Google and FSA (closed / same venue under a new company / no trace / unverified) |
| 4. Explain | `gen_reasons.py [--ids=…]` | Gemini hypotheses with evidence and counter-arguments; banned wording checked in code |
| 5. Venues | `build_venues.py` → `fill_hygiene.py` → `venue_competition.py` | FSA + Google merged into one card per venue, hygiene found locally or nationwide, competition within 300 m |
| 6. Customers & reviews | `gen_audience.py`, `gen_review_themes.py` | Who comes and what guests praise or criticise; every quote checked word for word |
| 7. Street context | `gen_hours.py`, `gen_footfall.py`, `street_history.py` | The street by the hour, TfL footfall proxy, turnover per street (time series + window functions) |
| 8. Atlas features | `create_search_indexes.py`, `stream_processor.json` + `start_stream_processor.js` | Atlas Search, Vector Search with Automated Embedding, the live Stream Processing pipeline |
| Site assets | `build_active_venues.py`, `build_venue_details.py`, `build_site.js` | Venue directory for the job screen, venue details for the timeline, the static build for Vercel |

Each script says at the top what it reads and writes. Paid API answers (Google, Gemini) are cached in `build/`, so re-runs cost nothing.
