# LeadOS — Working Memory

## Current branch
`codex/leados-rock-solid` (commit `048b3411`) — built on top of
`codex/leados-stabilization-merge` which has user's earlier merge.

## Branch ladder
```
codex/leados-rock-solid           048b3411  Rock-solid hardening (apify stub + legacy gate + manual)
codex/leados-stabilization-merge  6c894415  (current Railway deploy target)
                                  af43a43b  Harden lead truth hydration and signal promotion
                                  c2c452c8  Gate scoring + truth_state inspector UI (mine)
                                  624676f6  P0 social-merge fixes + drift guard (mine)
                                  60d71ce2  Harden lead truth hydration (handoff base)
```

## Latest commit `048b3411` does
1. **Stub `run_instagram_profile_scraper` on ApifyClient** -> kills the red error banner forever. Returns `{}`. Mirrored to deploy tree.
2. **Suppress `lead_state.last_error`** in `get_processed_details_for_lead` when `analysis_state == "analyzed"`. Stale errors no longer haunt successful re-analysis.
3. **Frontend `mergeProcessedDetails`** clears `error` field when latest state is `analyzed` (UI-layer defense).
4. **`_apply_read_time_judgment_gate`** — legacy scoring rows that lack `judgment_state` (saved before my gate landed) get gated at READ time. iSkin's `lead_tier: A, score: 96` now renders correctly without re-analysis.
5. **`docs/ENGINEERING_MANUAL.md`** — required-reading manual for every forward dev decision.
6. **`tests/test_rock_solid_fixes.py`** — 7 new cases. Total suite now 40/40 passing.

## Live API state (verified just now)
- Sapphire `dbc41522…`: `truth_state=verified_maps`, IG list clean, doctors=4, branches=2, score 91.
- Skin Vision `d09ccd44…`: `truth_state=website_proof`, doctors=`Dheemant M`, branch=`Annapurneshwari Nagar`. Coverage=2.
- iSkin `1592b115…`: `truth_state=cached_maps`, doctors=3, branches=3 (Uttarahalli, Bilekahalli, Nagawara), IG clean, no GPS handles.

The character-exploded URLs and GPS-coord IG handles bugs are GONE in production. The red apify banner will go away as soon as `048b3411` lands on `codex/leados-stabilization-merge` (or wherever Railway is currently watching).

## BLOCKED on credentials (same as before)
I cannot `git push` — the container has no GitHub PAT. Three options:
- Click **"Save to GitHub"** in the Emergent chat UI -> pushes both new branches.
- Paste a fine-grained GitHub PAT and I'll push directly.
- Manually pull on your Windows machine: `git fetch origin codex/leados-rock-solid` (after I'm pushed).

## After push, Railway/Vercel auto-deploy
- Backend redeploys from `.railway-backend-deploy/` once the branch is pushed (Railway watches the branch listed in its config; verify it's pointing at `codex/leados-rock-solid` after push, or merge the branch into whatever Railway is watching).
- Frontend redeploys from `frontend/`.

## Verification post-deploy
1. Hit `/health` -> should return healthy.
2. Curl all 3 lead IDs as in `docs/ENGINEERING_MANUAL.md` -> expect `truth_state` populated, no character-exploded IG, no GPS handles.
3. Open inspector for each lead -> expect:
   - colored truth-state pill in header (Verified / Cached verification / Website-verified)
   - NO red error banner
   - score cell shows numeric only when state >= website_proof, else "Needs verification"

## What's deferred (per the user's "limited credits, fix issues fast")
- Multiple "Analyze" buttons / start-stop dialogue UX consolidation. **Needs a UX pass with you.**
- 4 pre-existing drifted files (`agents/audit.py`, `discovery.py`, `config/loader.py`, `db/models.py`). CI gate now blocks new drift; resolving these needs you to confirm canonical side, then `make sync-fix` on a scoped branch.
- Daily-discovery cron (~30 min more work; not in this commit).
- Doctor-with-initials / branch-junk regression tests (need helper extraction; ~45 min).
- Re-analyze Skin Vision so its DB row picks up the enrichment fixes (one button click after deploy).

## Forward-dev rules (full list in `docs/ENGINEERING_MANUAL.md`)
1. Never edit only one tree (use `make sync-fix`).
2. Never invent verified facts.
3. Never let a stale state override a fresh one.
4. Gate every commercial judgment behind `_gate_judgment_for_sparse_truth` / `shouldGateConfidentJudgment`.
5. Wrap every external API call in try/except returning `{}`.
6. Add a regression test for every bug fix (the 40-test baseline must not shrink).
7. Add a `data-testid` to every interactive / outcome-bearing UI element.
