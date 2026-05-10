# LeadOS Working Memory

## Active Merge
This branch resolves `conflict_100526_1821` against GitHub `main`.

The branch includes the stabilization commits:
- `624676f6` social profile char-explosion and GPS-coordinate Instagram rejection.
- `c2c452c8` truth-state scoring gate and inspector rendering.
- `af43a43b` lead truth hydration and signal promotion.
- `6c894415` Instagram metrics fallback without actor dependency.
- `048b3411` stale Apify error suppression, legacy scoring read-time gate, and engineering manual.
- `8ce1d07d` / `69e64870` auto-generated follow-up changes from Emergent.

## Current Product Rules
- Do not fabricate ratings, reviews, doctors, locations, or social counts.
- Numeric commercial scores are only final when there is enough verified commercial truth.
- Sparse records must render as `Needs verification`, even if a legacy saved score exists.
- Stale backend errors must not override a newer successful analyzed state.
- Source and `.railway-backend-deploy` backend copies must stay in sync.

## Deploy Notes
- Railway uses `.railway-backend-deploy/`.
- Vercel uses `frontend/`.
- After deployment, verify `/health`, then re-run lead analysis for affected leads so saved rows pick up the latest enrichment and scoring gates.

## Regression Coverage
- `tests/test_lead_truth_consistency.py`
- `tests/test_scoring_truth_gate.py`
- `tests/test_rock_solid_fixes.py`

## Known Limit
Google Maps rating/review truth is only shown when real Maps data is attached or cached. If Apify Maps is out of quota, reviews/rating must remain unverified instead of being guessed.
