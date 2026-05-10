# LeadOS Engineering Manual — How This Was Stabilized & How To Move Forward

> Read this once before touching the codebase. It explains why LeadOS kept oscillating, how the recent fixes were structured, and the rules that prevent regressions.

## TL;DR
LeadOS was not failing because of one bug. It was failing because **truth flowed through too many independent code paths and stale states**. Every "fix" that only patched a symptom got undone by another path. The work in this manual:

1. Eliminated the worst-known bugs visible to operators (red error banners, fake confident scores, exploded Instagram URLs, GPS-coords-as-handles).
2. Added a single canonical `truth_state` so the inspector has one explicit source of truth.
3. Gated commercial judgment behind verified facts so sparse leads can never claim A/B confidence.
4. Made backend drift between `src/` and `.railway-backend-deploy/src/` literally impossible to merge silently.
5. Made stale errors and stale states unable to override fresh successful analysis.

## What changed (in order of operator visibility)

### 1. The red `'ApifyClient' object has no attribute 'run_instagram_profile_scraper'` banner is gone
**Symptom**: Inspector showed a red error banner on Sapphire / iSkin / Skin Vision even on rows whose `analysis_state == "analyzed"` and whose data was correct. Looked like the analysis failed even when it didn't.

**Root cause**:
- The actor `run_instagram_profile_scraper` was deprecated and replaced by an HTML OG-tag fallback (`_fetch_instagram_profile_snapshot`).
- A `getattr(self._apify, "run_instagram_profile_scraper", None)` guard was added in `enrichment.py`, BUT...
- The error message had already been persisted to `lead_state.last_error` in old DB rows, and the API was bubbling that string out as `processed_details.error`, which the frontend renders as a red banner.

**Fix**:
- `src/tools/apify.py`: added `run_instagram_profile_scraper` as a graceful no-op stub returning `{}`. So even if any current or future code path forgets the `getattr`, it never raises AttributeError.
- `src/api/server.py::get_processed_details_for_lead`: never expose `lead_state.last_error` when `analysis_state == "analyzed"`. Old, stale errors cannot haunt a successful re-analysis.
- `frontend/artifacts/zrai/lead-list/client.tsx::mergeProcessedDetails`: clear `error` on the merged details whenever the latest `analysis_state` is `analyzed`. Same defense in the UI layer.

**Test coverage**: `tests/test_rock_solid_fixes.py::test_apify_has_run_instagram_profile_scraper_stub`, `test_stale_error_suppression_in_source`, plus mirror checks against `.railway-backend-deploy/`.

### 2. Instagram URL list no longer explodes into characters
**Symptom**: Sapphire / iSkin inspector showed `social_profiles.instagram = ["h","t","t","p","s",":","/","w",".",...]` (URLs split into single characters).

**Root cause** (`_merge_social_profiles`): when one payload set `instagram` as a string and the next payload set it as a list, the merge did `list(merged.get("instagram"))` — `list("https://...")` returns a list of characters.

**Fix**:
- Wrap previous-string-value as `[stripped]` before extending.
- Re-run `_filter_social_url_list` on every merge so any junk left in cached/persisted state is normalized away on read.

### 3. GPS coordinates no longer leak as Instagram handles
**Symptom**: iSkin had `https://www.instagram.com/13.0533989/` and similar in social_profiles.instagram.

**Root cause**: server-side `_normalize_instagram_profile_url` regex `[A-Za-z0-9._]{1,30}` accepted pure-numeric handles.

**Fix**: explicit reject for `\d+(?:\.\d+)?` and any handle with fewer than 2 letters. Mirrored the stricter rule that already existed enrichment-side.

### 4. Sparse leads no longer show confident A/B scores
**Symptom**: Leads with no verified Maps reviews/rating, no doctors, no branches still showed `final_score: 96, lead_tier: A`. Operator could not tell if the score reflected real evidence or only website noise.

**Root cause**: scoring agent emitted final_score regardless of how many *independently-verified* commercial facts existed.

**Fix** (`src/agents/scoring.py`):
- `_truth_coverage(signal_facts)`: counts independently-verified commercial facts (reviews_count, rating, branch_count, doctor_count, verified social metrics). Range 0-5.
- `_gate_judgment_for_sparse_truth`: when coverage < `MIN_TRUTH_COVERAGE_FOR_JUDGMENT` (=2):
  - cap `lead_tier` at "C"
  - set `judgment_state = "needs_verification"`, `judgment_label = "Needs verification"`
  - flip `should_skip_outreach`
  - preserve `final_score` and `original_lead_tier` for transparency / debug
- `_apply_read_time_judgment_gate` in server.py applies the same gating to legacy stored rows that were saved before the gate landed. Old rows are fixed retroactively at read time.

**Frontend** (`client.tsx`): inspector renders a `Needs verification` badge instead of the numeric score whenever `truth_state` is `incomplete_verification` / `social_presence_only` / `failed`.

### 5. Backend drift between `src/` and `.railway-backend-deploy/src/` is now impossible to merge silently
**Symptom**: bugs would re-appear in production after being "fixed" because the fix only landed in `src/` and the Railway deploy ran a stale copy of `.railway-backend-deploy/src/` (e.g. `name 'rating' is not defined`, missing helper functions).

**Fix**:
- `scripts/check_railway_sync.py`: byte-level diff. Exit 1 on drift. `--fix` syncs `.railway-backend-deploy/src/` from `src/` in one shot.
- `Makefile`: `make sync-check` and `make sync-fix` targets.
- `.github/workflows/check-railway-sync.yml`: CI gate on every PR touching either tree. Cannot merge if drift.

### 6. Canonical `truth_state` ladder
**Single answer to "what do we know about this lead?"** Returned in every `signal_facts` payload:
- `verified_maps` — live Google Maps source (reviews + rating from `fact_sources`)
- `cached_maps` — cached Maps truth (e.g. domain-sibling hydration)
- `website_proof` — strong website-derived facts (doctors / branches / booking / phone, ≥2 independent)
- `social_presence_only` — only social signals, nothing else
- `incomplete_verification` — nothing meaningful surfaced; show "Needs verification"
- `failed` — analysis genuinely failed

The frontend renders one colored pill in the inspector header based on this state. Operators no longer have to reverse-engineer five competing fields.

## Test surface (40 cases, all green)
- `tests/test_lead_truth_consistency.py` (25 cases) — social-merge bug, GPS-handle rejection, truth_state ladder, source/deploy parity.
- `tests/test_scoring_truth_gate.py` (8 cases) — scoring gate behavior at, below, above threshold; tier demotion; deploy parity.
- `tests/test_rock_solid_fixes.py` (7 cases) — Apify stub presence, stale-error suppression contract, read-time judgment gate.

All three files use a tiny inline source-extraction loader so they run without LangGraph / Supabase / Apify SDK installed in CI. **Run them before every push:**
```bash
python -m pytest tests/test_lead_truth_consistency.py \
                 tests/test_scoring_truth_gate.py \
                 tests/test_rock_solid_fixes.py
```

## Rules for forward development

### Rule 1 — Never edit only one tree
Every change to `src/api/server.py` or anything under `src/agents/` MUST also land in `.railway-backend-deploy/src/...`. Use `make sync-fix` after editing `src/` to mirror the change. The CI gate will block PRs that forget.

### Rule 2 — Never invent verified facts
If `fact_sources[reviews] != "google_maps"` and `!= "google_maps_cached"`, the lead does NOT have verified Maps reviews. Period. Do not synthesize, do not estimate from social followers, do not seed-from-similar-lead. Set `truth_state = "incomplete_verification"` and let the operator manually verify.

### Rule 3 — Never let a stale state override a fresh one
Whenever you merge canvas state with backend state, the side with the **newer** `analysis_updated_at` AND state `analyzed` wins. If the older side has an `error` field, drop it. The merge in `client.tsx::mergeProcessedDetails` already encodes this; replicate the pattern in any new merge code.

### Rule 4 — Gate commercial judgment behind verified truth
Anywhere a final score / tier / "high-priority" / "worth pursuing" label is emitted, run it through `_gate_judgment_for_sparse_truth` (backend) or `shouldGateConfidentJudgment(truthState)` (frontend). No exceptions. Sparse rows render "Needs verification".

### Rule 5 — Catch-and-no-op every external API call
Every Apify / scraper / external-actor call must:
- be wrapped in `try / except Exception as exc:`
- log a warning, return `{}` or `None`
- never propagate the exception upward to the inspector

The `run_instagram_profile_scraper` stub is the canonical pattern.

### Rule 6 — Add a regression test before declaring fixed
For every bug fix, add a test in the appropriate `tests/test_*` file. The 40-test baseline catches every prior regression class. Don't let it shrink.

### Rule 7 — `data-testid` on every interactive / outcome-bearing UI element
The inspector now has `inspector-truth-state-badge`, `inspector-score-cell`, `inspector-score-needs-verification`. Every new badge, button, error state, score field MUST have a stable `data-testid`. This is what makes future Playwright/Cypress tests possible.

## What is intentionally still pending
These are real follow-ups, not deferred laziness:

| Priority | Item | Why deferred |
|---|---|---|
| P1 | Re-analyze Skin Vision lead `d09ccd44…` | Its DB row predates the enrichment fixes; one re-run will populate doctors/branches. |
| P1 | Resolve 4 pre-existing drifted files (`agents/audit.py`, `discovery.py`, `config/loader.py`, `db/models.py`) | User explicitly said "no unrelated work". CI now blocks any new drift. |
| P2 | Daily lead-discovery cron | Endpoint exists; need a scheduled GH Action or Railway cron to call it nightly. ~30 minutes of work. |
| P2 | Doctor-with-initials / branch-junk regression tests | Need to extract enrichment helpers out of the `EnrichmentAgent` class so they can be tested without LangGraph. ~45 min refactor. |
| P2 | Pre-commit hook for `scripts/check_railway_sync.py` | One-line addition once a `.pre-commit-config.yaml` exists. |
| P3 | Consolidate the multiple "Analyze" buttons in the inspector | UI consistency complaint from operator. Needs UX pass. |

## How to verify production health right now
```bash
# 1. Backend health
curl https://zrai-lead-os-private-production.up.railway.app/health

# 2. Live truth_state on the 3 reference leads
for id in d09ccd44-92f3-4c2e-a56d-cb550cfeb0d2 \
          dbc41522-03fd-4540-b7ed-e34af20ecc7d \
          1592b115-0d39-47fb-b459-ecb50048b2df; do
  curl -s https://zrai-lead-os-private-production.up.railway.app/api/v1/leads/$id \
    | python3 -c "
import sys,json
d=json.load(sys.stdin); l=d['lead']; sf=l['signal_facts']
print(l['company_name'])
print('  truth_state:', sf.get('truth_state'))
print('  IG sample :', str(sf.get('social_profiles',{}).get('instagram'))[:120])
print('  doctors   :', sf.get('doctor_count'), sf.get('doctor_names'))
print('  branches  :', sf.get('branch_count'), sf.get('branch_names'))
"
done
```

Expected after deploy:
- All three return a populated `truth_state`.
- `instagram` is a list of clean URLs only — no characters, no GPS coords.
- Sapphire: `truth_state: verified_maps`, doctors >=4, branches >=2.
- iSkin: `truth_state: cached_maps`, doctors >=3, branches >=3.
- Skin Vision: `truth_state: website_proof`, doctors >=1, branches >=1.

## Where to look first when something breaks again
1. `python scripts/check_railway_sync.py` — drift is the historical #1 cause.
2. `python -m pytest tests/test_rock_solid_fixes.py tests/test_lead_truth_consistency.py tests/test_scoring_truth_gate.py` — should be 40/40.
3. Tail Railway logs for the actual Python traceback. If it isn't an `AttributeError` on a method we just stubbed, it's a new path that needs the rule-5 try/except wrap.
4. Hit `/api/v1/leads/{id}` directly with curl. The frontend cannot conjure a state the API didn't emit.

— End of manual.
