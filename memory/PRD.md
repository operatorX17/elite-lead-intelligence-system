# ZRAI Lead OS — PRD (Live)

**Repo of truth**: https://github.com/operatorX17/elite-lead-intelligence-system.git
**Working branch**: `master`
**Local working copy**: `/app/repo` (cloned from the public repo above)
**Production deploy**: Railway (auto-redeploy on push to master)

---

## Original problem statement (Jan 2026 stabilization brief)

ZRAI Lead OS — a lead intelligence engine for clinics — was reliably producing
backend data but the UI felt unstable: stale errors, blank fields, weak
rendering, confusing scoring, and not enough credit given to doctor IG
followings (which is real demand/trust proof for clinic leads).

Backend lives in **two mirrored trees** (rule: every backend fix lands in BOTH):
- `src/`
- `.railway-backend-deploy/src/`

Frontend is Next.js under `frontend/` (lead inspector lives in
`frontend/artifacts/zrai/lead-list/client.tsx` and
`frontend/artifacts/zrai/lead-card/client.tsx`).

---

## Architecture (current)

| Layer       | Tech                                                   |
|-------------|--------------------------------------------------------|
| Frontend    | Next.js 15 + React + Tailwind, deployed on Vercel      |
| Backend     | FastAPI + LangGraph multi-agent pipeline, on Railway   |
| DB          | Supabase (Postgres) + Pinecone (vector)                |
| Scrapers    | Apify (Maps, IG bio, YouTube), Firecrawl, Steel        |
| LLMs        | OpenRouter / Gemini / Anthropic via emergentintegrations |

Agents (LangGraph `StateGraph`, see `src/graph/`):
discovery → enrichment → intent → audit → scoring → outreach → governance.

---

## Jan 2026 stabilization session (what shipped today)

**Files modified** (mirrored in src/ AND .railway-backend-deploy/src/):
- `src/api/server.py` — error sanitizer + read-time scrub + write-time scrub +
  verified-social treats doctor IG + **`_try_return_cached_analysis` cache-first guard**
- `src/agents/enrichment.py` — doctor IG profile enrichment (HTML fallback)
- `src/agents/scoring.py` — doctor followers count for demand & trust
- Frontend: `lead-list/client.tsx`, `lead-card/client.tsx`, `lib/zrai/types.ts`,
  new `lib/zrai/sanitize-error.ts`
- Tests: new `tests/test_elite_stabilization_jan26.py` (18 tests) +
  new `tests/test_stability_no_auto_burn_jan26.py` (11 tests)

**Behaviors fixed**:
1. **Stop burning credits**: `execute_lead_analysis` now short-circuits when
   `force_refresh=False` and the lead is already `analyzed`. Verified at
   runtime with mocks: pipeline does NOT run, payload returned with
   `from_cache: True`.
2. **Auto-analyze defaults OFF**: `autoAnalyzeEnabled = false` is the only
   default in the lead-list now (was `true`). Opening the canvas no longer
   triggers a background re-run.
3. **Toolbar split**: "Analyze N new" (cache-first, default) + "Re-analyze
   all" (confirm-guarded, force_refresh, only when needed).
4. **Keyboard shortcut "Analyze visible"** also runs cache-first and skips
   already-analyzed leads.
5. **Inspector NEVER shows raw Python errors** any more (`'ApifyClient' object…`,
   tracebacks, AttributeErrors). Both at read time (sanitized in API response)
   and at write time (sanitized before persistence) and as a defense-in-depth
   layer in the frontend (`sanitizeOperatorError`).
6. **Stale-error suppression**: when `analysis_state == "analyzed"`, the error
   banner is fully hidden in lead-list and lead-card.
7. **Doctor IG profiles** are enriched (up to 4 doctors per clinic) via the
   public HTML fallback, attached to each `doctor_profile` dict, and
   aggregated into `doctor_followers_total` / `doctor_max_followers` /
   `doctor_instagram_profiles` on signal_facts.
8. **Scoring** uses `combined_followers = clinic_followers + doctor_followers_total`
   for demand+trust, and `_has_meaningful_verified_social` now treats
   doctor followers as a first-class verified social fact.
9. **Verification badges** in the inspector: verified Maps · cached Maps ·
   website-verified · social presence only · needs verification.
10. **Doctor Social Proof section** in the lead-card: lists each doctor with
    IG followers/posts and a deep link to their profile.
11. **Single intuitive "Analyze" / "Re-analyze" CTA** in the lead-card
    (replaced the confusing "Analyze lead" + "Refresh truth" duo).
12. **Live X / Y analyzed counter** in the toolbar.
13. **GPS-coordinate-looking IG handles** (e.g. `17.4456,78.4123`) rejected.

**Tests**: 73 / 73 pass + runtime verification of cache-first guard.
```
python -m pytest tests/test_stability_no_auto_burn_jan26.py \
  tests/test_elite_stabilization_jan26.py \
  tests/test_lead_truth_consistency.py \
  tests/test_scoring_truth_gate.py \
  tests/test_rock_solid_fixes.py \
  tests/test_social_profile_validation.py -q
```

**Compile guard**: `python -m py_compile` clean across both backend trees:
- `src/api/server.py` + `.railway-backend-deploy/src/api/server.py`
- `src/agents/enrichment.py` + `.railway-backend-deploy/src/agents/enrichment.py`
- `src/agents/scoring.py` + `.railway-backend-deploy/src/agents/scoring.py`
- `src/tools/apify.py` + `.railway-backend-deploy/src/tools/apify.py`

---

## How to push from Emergent → GitHub → Railway live

1. In Emergent chat input, click **"Save to GitHub"**.
2. Pick repo `operatorX17/elite-lead-intelligence-system`, branch `master`.
3. Click **"PUSH TO GITHUB"**.
4. Railway auto-redeploys on the new master commit.
5. Test live.

If GitHub flags conflicts, push to a new branch from Emergent and merge on GitHub.

---

## Backlog / next sessions (P0 → P2)

**P0 — finish the elite UX polish**
- Inspector visual redesign: clear sections — Score · Why Pursue · Demand
  Proof · Trust Proof · Leaks · Contacts · Doctor/Social · Next Action.
  (Today the data is all there, layout is still grid-heavy.)
- "Maps not verified" banner (instead of blank rating cell) when Apify
  Maps quota is exhausted — currently the cell just shows "-".

**P1 — sales engine sharpening**
- Outreach drafts auto-personalized per detected demand source
  (clinic IG vs. specific doctor IG vs. Maps reviews).
- Inbox view that groups by `truth_state` so operators triage A-tier
  verified-Maps leads first.

**P2 — multi-agent upgrade (research-only this session)**
- Migrate the linear LangGraph pipeline to a hierarchical
  supervisor-of-swarms (LangGraph 1.2 supports it natively). Currently
  a single supervisor calls each agent in sequence; a swarm of
  specialists (Maps, IG, YouTube, doctor-search) hands off via
  `Command` for lower latency + lower token cost.

---

## Smart enhancement (one-line revenue idea)

Today the inspector shows _what_ is leaking (no booking, no WhatsApp).
The next mile: show **per-leak revenue at risk** in INR — even a rough
"~₹X/month leaked at current rating × reviews × ticket size" line in the
inspector turns this from a diagnosis tool into a closing tool. You
already have rating + reviews + category; multiply by an industry-typical
visit ticket and a 30-day window. One number that forces the operator
to pick up the phone.

---

## Key creds / env

Lives in Railway / Vercel project settings. The Emergent dev workspace
does not need them; backend/frontend boot here only for testing and
all real keys come from the deployed envs. Do NOT commit `.env`.
