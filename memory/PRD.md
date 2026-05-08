# ZRAI Lead OS — PRD / Working Memory

## Original problem statement (handoff: codex/palate-twilio-demo @ 60d71ce2)
Stabilize ZRAI Lead OS into a reliable daily lead intelligence operator. Lead
inspector was showing sparse or wrong commercial truth: missing reviews/rating/
doctors/locations/socials, weak judgment, duplicate leads not inheriting known
truth, stale saved canvas artifacts, and backend/frontend drift between
`src/` and `.railway-backend-deploy/src/`.

## Tech / arch
- Backend: FastAPI + Supabase (Python 3.11). Source under `src/`. Railway
  deploys from a *mirror* tree at `.railway-backend-deploy/src/`. Drift between
  the two is the single biggest historical source of recurring runtime bugs.
- Frontend: Next.js (Vercel) at `frontend/` with a lead-list canvas
  artifact in `frontend/artifacts/zrai/lead-list/client.tsx`.
- Live URLs: https://zrai-lead-os.vercel.app and
  https://zrai-lead-os-private-production.up.railway.app/health.

## Active leads used as ground truth
- Skin Vision Clinic d09ccd44-92f3-4c2e-a56d-cb550cfeb0d2 (skinvision.co.in)
- Sapphire Skin & Aesthetics dbc41522-03fd-4540-b7ed-e34af20ecc7d (sapphireskin.in)
- iSkin Clinic 1592b115-0d39-47fb-b459-ecb50048b2df (iskinclinic.in)

## Bugs found in live `/api/v1/leads/{id}` during this session
1. social_profiles.instagram exploded into single characters
   (`["h","t","p","s",":","/","w",".","i","n",...]`) on Sapphire and iSkin.
2. GPS coordinates leaking as Instagram handles on iSkin
   (`https://www.instagram.com/13.0533989/`, `12.8877892`, `12.9103096`).
3. Skin Vision returning 0 doctors / 0 branches / null rating despite the
   handoff saying these should be extractable. Needs re-analysis after deploy.
4. Pre-existing drift in 4 files between `src/` and `.railway-backend-deploy/src/`
   (`agents/audit.py`, `agents/discovery.py`, `config/loader.py`, `db/models.py`).

## What was implemented this session (commit 1820e937)
- `src/api/server.py` + `.railway-backend-deploy/src/api/server.py`:
  - Fixed `_merge_social_profiles` so a string payload followed by a list
    payload no longer explodes the URL into characters.
  - Tightened `_normalize_instagram_profile_url` to reject pure-numeric /
    decimal handles (GPS coords) and any handle with fewer than 2 letters.
  - Added `_filter_social_url_list` which re-normalizes every social URL list
    inside `_merge_social_profiles` on every read, so junk in cached/persisted
    state is filtered out automatically.
  - Added `_derive_truth_state` and `_truth_state_label` and injected
    `truth_state`, `truth_state_label`, `commercial_truth_coverage` into
    every signal_facts payload returned by `build_signal_facts`. States:
    verified_maps / cached_maps / website_proof / social_presence_only /
    incomplete_verification / failed.
- `scripts/check_railway_sync.py`: byte-level diff of `src/` vs
  `.railway-backend-deploy/src/`. `--fix` syncs deploy from source.
- `.github/workflows/check-railway-sync.yml`: CI gate on PRs touching either
  tree. Permanently kills the silent-drift class of bugs.
- `Makefile`: new `sync-check` and `sync-fix` targets.
- `tests/test_lead_truth_consistency.py`: 25 regression cases, all green.
  Covers the social-merge bug, GPS-handle rejection, the truth_state ladder,
  and parity between source and deploy trees.

## What is verified
- Both source trees are byte-identical for the files I touched (server.py,
  enrichment.py, contact_intelligence.py, scoring.py).
- `python -m pytest tests/test_lead_truth_consistency.py` -> 25/25 passing.
- `python -m py_compile ...` clean for all 8 backend files.
- Live `/health` returns 200 from Railway (still pre-deploy of this commit).

## What is still pending
- **Push commit `1820e937` to GitHub** -> auto-triggers Railway + Vercel.
  Use the "Save to GitHub" button in the Emergent chat UI, or pass a PAT.
- **Re-verify live API after redeploy** for the 3 lead IDs above; expect
  - Sapphire/iSkin: social_profiles.instagram is clean URLs only,
  - iSkin: no GPS-coord IG handles,
  - every signal_facts payload exposes a `truth_state` field.
- **Re-analyze Skin Vision** so doctors/branches surface in DB.

## Pre-existing drift NOT addressed (per "do not stage unrelated work")
Flagged but left untouched; CI now blocks regressing further:
- src/agents/audit.py, src/agents/discovery.py, src/config/loader.py, src/db/models.py
Run `make sync-fix` on a scoped branch once the team confirms canonical side.

## Backlog
- P1: Wire `truth_state` into inspector UI in
  `frontend/artifacts/zrai/lead-list/client.tsx` so sparse leads render
  "Needs verification" instead of a confident score.
- P1: Gate `final_score` in `src/agents/scoring.py` on
  `commercial_truth_coverage >= 2`.
- P1: Resolve the 4 pre-existing drift files (`make sync-fix` on a scoped branch).
- P2: Add doctor-with-initials and branch-junk regression tests once
  enrichment helpers are extractable (currently inside EnrichmentAgent class).
- P2: Pre-commit hook for `scripts/check_railway_sync.py`.
