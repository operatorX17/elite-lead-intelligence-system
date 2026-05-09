# ZRAI Lead OS / LeadOS — PRD / Working Memory

## Current branch (per user's last instruction)
- Active development branch: **`codex/leados-stabilization`** (created from `codex/palate-twilio-demo` HEAD).
- All future stabilization work goes here.
- `codex/palate-twilio-demo` retains commit `1820e937` (P0 social-merge fixes + drift guard) but is no longer the working branch.

## Branch state in container
```
codex/leados-stabilization   43c1cb83  Gate scoring + render truth_state in inspector (LeadOS stabilization)
codex/palate-twilio-demo     92db9bec  Auto-generated changes
                             1820e937  Fix social_profiles char-explosion + GPS-coord IG handles, add truth_state and drift guard
                             60d71ce2  Harden lead truth hydration and clinic extraction (handoff base)
```

## What was implemented (commits 1820e937 + 43c1cb83)

### Backend — `src/api/server.py` + `.railway-backend-deploy/src/api/server.py`
- `_merge_social_profiles`: no longer explodes URL strings into individual chars when string and list payloads are merged. Re-runs `_filter_social_url_list` on every read so junk in cached/persisted state is normalized away.
- `_normalize_instagram_profile_url`: rejects pure-numeric / decimal handles (GPS coords like `13.0533989`) and any handle with <2 letters.
- `_derive_truth_state` + `_truth_state_label`: canonical 5-state ladder (`verified_maps` / `cached_maps` / `website_proof` / `social_presence_only` / `incomplete_verification` / `failed`).
- Every `signal_facts` payload now exposes `truth_state`, `truth_state_label`, `commercial_truth_coverage`.

### Backend — `src/agents/scoring.py` + Railway mirror
- `_truth_coverage`: counts independently-verified commercial facts (reviews, rating, branches, doctors, verified social metrics).
- `_gate_judgment_for_sparse_truth`: caps `lead_tier` at C, sets `judgment_state="needs_verification"`, flips `should_skip_outreach` when coverage < 2. `final_score` preserved for transparency, `original_lead_tier` saved for debug.
- Wired into `ScoringAgent.run` after `final_score` computation.

### Frontend — `frontend/artifacts/zrai/lead-list/client.tsx` + `frontend/lib/zrai/types.ts`
- `SignalFacts` type adds `truth_state`, `truth_state_label`, `commercial_truth_coverage`.
- Inspector header renders a colored truth-state pill (`Verified` / `Cached verification` / `Website-verified` / `Social presence only` / `Needs verification` / `Verification failed`).
- Inspector score cell renders a `Needs verification` badge instead of the numeric score when state is `incomplete_verification`, `social_presence_only`, or `failed`.
- `data-testid`s added: `inspector-truth-state-badge`, `inspector-score-cell`, `inspector-score-needs-verification`.

### Drift prevention (permanent)
- `scripts/check_railway_sync.py` — byte-level diff src/ vs `.railway-backend-deploy/src/`. `--fix` syncs.
- `Makefile` — `make sync-check` / `make sync-fix`.
- `.github/workflows/check-railway-sync.yml` — CI gate on PRs touching either tree.

### Regression tests (33 total, all green)
- `tests/test_lead_truth_consistency.py` (25 cases) — social-merge bug, GPS handle rejection, truth_state ladder, source/deploy parity.
- `tests/test_scoring_truth_gate.py` (8 cases) — coverage counting, gating below/at/above threshold, score preservation, deploy-tree parity.

Both files use a tiny inline loader so they run without LangGraph/Supabase deps installed.

## Verified locally
- `python -m py_compile` clean for all 8 backend files.
- `python -m pytest tests/test_lead_truth_consistency.py tests/test_scoring_truth_gate.py` → 33 passed.
- `python scripts/check_railway_sync.py` shows my files are in sync (only the 4 pre-existing drift files remain).
- Frontend TS errors are environmental (no `node_modules` in container) — Vercel build will resolve them.

## BLOCKED — push to GitHub
I cannot push from this container — no GitHub PAT here. `git push origin <branch>` returns `fatal: could not read Username for 'https://github.com'`.

To unblock:
- click **"Save to GitHub"** in the Emergent chat UI (one click pushes both branches), OR
- paste a fine-grained GitHub PAT with `Contents: Read and write` on the repo, then I'll push directly.

After push:
- `codex/palate-twilio-demo` advances to `1820e937` (or further if auto-commits go too).
- `codex/leados-stabilization` is created on origin at `43c1cb83`.
- Railway autodeploys backend (watches the repo + `.railway-backend-deploy/`).
- Vercel autodeploys frontend (watches `frontend/`).

## Verification steps once deployed
```bash
# 1. Check backend health
curl https://zrai-lead-os-private-production.up.railway.app/health

# 2. Verify the Sapphire and iSkin Instagram payloads are clean
for id in dbc41522-03fd-4540-b7ed-e34af20ecc7d 1592b115-0d39-47fb-b459-ecb50048b2df; do
  curl -s https://zrai-lead-os-private-production.up.railway.app/api/v1/leads/$id \
    | python3 -c "
import sys,json
d=json.load(sys.stdin); sf=d['lead']['signal_facts']
print(d['lead']['company_name'])
print('  truth_state:', sf.get('truth_state'))
print('  instagram :', sf.get('social_profiles',{}).get('instagram'))
"
done
```

Expected:
- No single-character entries in `social_profiles.instagram`.
- No `13.0533989` / `12.8877892` / `12.9103096` URLs.
- `truth_state` field present on every payload.

## Pre-existing drift NOT addressed (per "do not stage unrelated work")
4 files differ between `src/` and `.railway-backend-deploy/src/`:
- `agents/audit.py` — different page-crawl limits (8 vs 5)
- `agents/discovery.py`
- `config/loader.py`
- `db/models.py`

The CI gate now catches this on the next PR; running `make sync-fix` from a scoped branch resolves them once the team confirms which side is canonical.

## Backlog
- P1: Re-analyze the 3 active leads after deploy so DB rows pick up the enrichment fixes. Skin Vision (`d09ccd44…`) in particular is still showing 0 doctors / 0 branches because its row predates the fixes.
- P2: Extend `tests/test_lead_truth_consistency.py` with doctor-with-initials and branch-junk regression cases (need helper extraction from `EnrichmentAgent` class).
- P2: Pre-commit hook calling `scripts/check_railway_sync.py` so drift is caught before push.
- P2: Resolve the 4 pre-existing drift files via `make sync-fix` on a scoped branch.
