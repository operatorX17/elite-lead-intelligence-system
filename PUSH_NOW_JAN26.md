# Push these changes to GitHub → Railway live (Jan 2026)

## What changed
9 files, +708 / -49 lines. New file: `frontend/lib/zrai/sanitize-error.ts`,
`tests/test_elite_stabilization_jan26.py`. Backend trees stay mirrored.

## How to ship
1. Click **Save to GitHub** in the Emergent chat input.
2. Repo: `operatorX17/elite-lead-intelligence-system`, branch: `master`.
3. **PUSH TO GITHUB**.
4. Railway auto-redeploys. Test live.

## Local sanity check (optional)
```bash
python -m py_compile src/api/server.py .railway-backend-deploy/src/api/server.py \
  src/agents/enrichment.py .railway-backend-deploy/src/agents/enrichment.py \
  src/agents/scoring.py .railway-backend-deploy/src/agents/scoring.py \
  src/tools/apify.py .railway-backend-deploy/src/tools/apify.py

python -m pytest tests/test_lead_truth_consistency.py \
  tests/test_scoring_truth_gate.py tests/test_rock_solid_fixes.py \
  tests/test_social_profile_validation.py \
  tests/test_elite_stabilization_jan26.py -q
```
Expected: `62 passed`.

## What now works
- Inspector never shows raw Python errors / Apify AttributeErrors.
- Doctor IG followers count as demand/trust (not just clinic IG).
- Verification badge on every lead (verified Maps / cached Maps /
  website-verified / social only / needs verification).
- ONE Analyze / Re-analyze button per lead in the card view.
- Stale error banners auto-clear when re-analysis succeeds.
