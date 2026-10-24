# Components and data contract

## Shared components

| Component / selector | Responsibility |
| --- | --- |
| `.site-header`, `.brand`, `.site-footer` | Navigation, identity and footer |
| `.segmented` | Owner/worker switch with pressed state |
| `.search-box`, `.compact-search` | Labelled search controls |
| `.badge` | Explicit evidence or confidence label; colour is supplementary |
| `.source`, `.sources` | Source label or verified source link; date status |
| `.filter-group` | All / confirmed / probable / possible / entity_change |
| `.map-panel`, `.pin`, `.map-legend` | Leaflet map, accessible case markers and legend |
| `.case-tile` | Address summary linking to a full case |
| `.timeline` | Legal-entity records; dates and lifespan |
| `.hypothesis`, `.counter` | Reason, supporting evidence, confidence, counterargument |
| `.metric` | Nearby venue count or distance with source scope |
| `.now-row` | Current/recent listing, source, available rating date |
| `.alert`, `.disclaimer` | Local caveat and overall scope |
| `.status-panel`, `.signal-row` | Employer signals and missing checks |
| `.checklist`, `.help-links` | Questions for the employer and official help |
| `.share-card`, `.qr` | Portable case summary and real generated QR |
| `.empty`, `.loading`, `#toast` | Empty, loading and short status feedback |

## Exact API fields used

| Field | View / treatment |
| --- | --- |
| `id` | Query-string routing and QR target |
| `address` | Heading, list title, search and marker label |
| `location.coordinates` | Leaflet reverses GeoJSON `[lng,lat]` to `[lat,lng]` |
| `closure_level` | Filters and case evidence badge; enum unchanged |
| `dist_hub_m` | Distance from dataset hub (not assumed to be station distance) |
| `chain[].name` | Legal name in timeline and search |
| `chain[].opened`, `.closed` | Company-record date range, unknown if absent |
| `chain[].months` | Company lifespan, not restaurant lifespan |
| `chain[].company_number` | Optional Companies House record link |
| `chain[].verification.verdict` | `closed_google`, `no_trace`, `unclear`, `operating_now` label |
| `chain[].verification.note` | Original note; temporary-closure qualifier when provided |
| `chain[].verification.evidence[]` | Optional Google place-record link |
| `now_here[].name`, `.src` | Listing name and source |
| `now_here[].rating_date`, `.hygiene`, `.rating` | Optional rating information; never fabricated |
| `context.nearest_station.name`, `.m` | Station name and distance |
| `context.venues_within_150m_FSA` | Nearby FSA venue count |
| `analysis.headline` | Hypothesis section introduction |
| `analysis.hypotheses[].reason` | Hypothesis title |
| `analysis.hypotheses[].evidence[]` | Supporting observations |
| `analysis.hypotheses[].confidence` | Labelled model confidence (`low`, `medium`, `high`) |
| `analysis.hypotheses[].counter_argument` | Counterargument in a distinct inset |
| `analysis.caveat` | Uncertainty section |

Sample analysis is translated in a separate English fixture; other cases use an explicit untranslated/not-supplied state. Raw JSON is never changed.

## Suggested future API additions (not required or implemented)

Source-specific `checked_at`, source record URLs for FSA, structured Google business status instead of parsing `verification.note`, verified venue trading dates separate from company dates, and employer legal-entity match provenance. These are requests for future integration, not fields assumed by this design.

## Ownership

Claude owns app/data/API/deployment. This handoff is entirely inside `design/`. Copy or adapt CSS and template functions rather than replacing the app directory. No shared dependency manifests or project-level settings were changed.
