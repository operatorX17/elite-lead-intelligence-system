# 🚀 Push to operator-x17 GitHub (Private Repo)

## Step 1: Initialize Git (if not already done)

```bash
git init
git add .
git commit -m "Initial commit: ZRAI Lead OS v1.0 with scoring fix"
```

## Step 2: Create Private Repo on GitHub

1. Go to: https://github.com/new
2. **Owner:** Select `operator-x17`
3. **Repository name:** `zrai-lead-os`
4. **Description:** "AI-powered lead intelligence system for Indian healthcare - ₹5L/month in 30 days"
5. **Visibility:** ✅ **Private** (IMPORTANT!)
6. **DO NOT** initialize with README, .gitignore, or license
7. Click "Create repository"

## Step 3: Push to GitHub

```bash
# Add remote (replace with your actual repo URL)
git remote add origin https://github.com/operator-x17/zrai-lead-os.git

# Push to main branch
git branch -M main
git push -u origin main
```

## Step 4: Verify .gitignore

Make sure these are in `.gitignore` (already configured):

```
# Secrets
.env
.env.local
*.key
*.pem

# API Keys
*secret*.json
*credentials*.json

# Output
output/
screenshots/
*.csv
*.json
!package.json
!tsconfig.json

# Python
__pycache__/
*.pyc
.pytest_cache/
.hypothesis/

# Node
node_modules/
.next/

# Database
*.db
*.sqlite
```

## Step 5: Verify Secrets Are NOT Pushed

Check that these files are NOT in the repo:
- ❌ `.env` (contains API keys)
- ❌ `output/` (contains lead data)
- ❌ `*secret*.json` (Google OAuth)
- ❌ `__pycache__/` (Python cache)

## Step 6: Add Collaborators (Optional)

If you want to add team members:
1. Go to: https://github.com/operator-x17/zrai-lead-os/settings/access
2. Click "Add people"
3. Enter their GitHub username
4. Select permission level (Write/Admin)

## Alternative: Use GitHub CLI

If you have GitHub CLI installed:

```bash
# Login to operator-x17 account
gh auth login

# Create private repo
gh repo create operator-x17/zrai-lead-os --private --source=. --remote=origin

# Push code
git push -u origin main
```

## What Gets Pushed

✅ **Code:**
- `lead_os.py` - Main pipeline
- `src/` - All agents and tools
- `config/` - Configuration files
- `tests/` - Test suite
- `frontend/` - Next.js frontend
- `migrations/` - Database schemas

✅ **Documentation:**
- `README.md` - Project overview
- `SCORING_FIX_JAN25.md` - Latest fix
- `FIX_COMPLETE_JAN25.md` - Proof of fix
- All other `.md` files

❌ **NOT Pushed (in .gitignore):**
- `.env` - API keys
- `output/` - Lead data
- `__pycache__/` - Python cache
- `node_modules/` - Dependencies
- `.hypothesis/` - Test data

## Verify Push Success

After pushing, check:
1. Go to: https://github.com/operator-x17/zrai-lead-os
2. Verify it shows "Private" badge
3. Check files are there
4. Verify `.env` is NOT visible
5. Check commit history

## Clone on Another Machine

To clone this repo on another machine:

```bash
git clone https://github.com/operator-x17/zrai-lead-os.git
cd zrai-lead-os

# Copy .env.example to .env and add your keys
cp .env.example .env
nano .env  # Add your API keys

# Install dependencies
pip install -r requirements.txt
cd frontend && npm install

# Run test
python lead_os.py --city "Bangalore" --n 10 --niche "diagnostics"
```

## Troubleshooting

### Error: "remote origin already exists"
```bash
git remote remove origin
git remote add origin https://github.com/operator-x17/zrai-lead-os.git
```

### Error: "Authentication failed"
```bash
# Use personal access token instead of password
# Generate token at: https://github.com/settings/tokens
# Use token as password when prompted
```

### Error: "Permission denied"
```bash
# Make sure you're logged in as operator-x17
# Check with: git config user.name
# Set with: git config user.name "operator-x17"
```

## Repository Settings (Recommended)

After pushing, configure these settings:

1. **Branch Protection:**
   - Settings → Branches → Add rule
   - Branch name: `main`
   - ✅ Require pull request reviews
   - ✅ Require status checks

2. **Secrets:**
   - Settings → Secrets → Actions
   - Add: `SUPABASE_URL`, `SUPABASE_KEY`, `OPENROUTER_API_KEY`, etc.

3. **Collaborators:**
   - Settings → Collaborators
   - Add team members with appropriate permissions

---

**Status:** Ready to push
**Repo:** https://github.com/operator-x17/zrai-lead-os
**Visibility:** Private ✅
**Branch:** main
