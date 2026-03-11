# Push to GitHub - operator-x17 Account

## 🎯 Quick Commands

### Step 1: Initialize Git (if not already done)
```bash
git init
git add .
git commit -m "Initial commit - ZRAI Lead OS v1.0"
```

### Step 2: Add Remote (operator-x17 account)
```bash
# Replace REPO_NAME with your desired repository name
git remote add origin https://github.com/operator-x17/REPO_NAME.git
```

### Step 3: Create Private Repo on GitHub
Go to: https://github.com/new
- Owner: operator-x17
- Repository name: zrai-lead-os (or your choice)
- **Make it PRIVATE** ✅
- Don't initialize with README (we already have one)

### Step 4: Push to GitHub
```bash
git branch -M main
git push -u origin main
```

---

## 🔐 If You Need Authentication

### Option A: Personal Access Token (Recommended)
1. Go to: https://github.com/settings/tokens
2. Generate new token (classic)
3. Select scopes: `repo` (full control)
4. Copy the token
5. Use it as password when pushing:
   ```bash
   Username: operator-x17
   Password: <paste-your-token>
   ```

### Option B: SSH Key
```bash
# Generate SSH key
ssh-keygen -t ed25519 -C "your-email@example.com"

# Add to GitHub
# Copy the public key:
cat ~/.ssh/id_ed25519.pub

# Add it at: https://github.com/settings/keys

# Change remote to SSH:
git remote set-url origin git@github.com:operator-x17/REPO_NAME.git
```

---

## 📦 What Will Be Pushed

### Core System:
- ✅ `lead_os.py` - Main LEAD OS pipeline
- ✅ `src/` - All agents, tools, config
- ✅ `config/` - YAML configurations
- ✅ `migrations/` - Database schemas
- ✅ `tests/` - Test files
- ✅ `frontend/` - Full frontend

### Documentation:
- ✅ `README.md`
- ✅ `LEAD_OS_READY.md`
- ✅ All status/guide docs

### Excluded (via .gitignore):
- ❌ `.env` (secrets)
- ❌ `node_modules/`
- ❌ `__pycache__/`
- ❌ `output/` (generated files)
- ❌ `screenshots/`

---

## 🚀 Complete Script

```bash
# 1. Check current status
git status

# 2. Add all files
git add .

# 3. Commit
git commit -m "ZRAI Lead OS v1.0 - Complete system with LangGraph + OpenRouter"

# 4. Add remote (replace REPO_NAME)
git remote add origin https://github.com/operator-x17/zrai-lead-os.git

# 5. Push
git push -u origin main
```

---

## ⚠️ Before Pushing - Check .gitignore

Make sure `.env` is in `.gitignore`:
```bash
# Check if .gitignore exists
cat .gitignore

# If not, create it:
echo ".env
.env.local
__pycache__/
*.pyc
node_modules/
.DS_Store
output/
screenshots/
checkpoints/
*.log" > .gitignore
```

---

## 🔧 If You Get Errors

### Error: "remote origin already exists"
```bash
git remote remove origin
git remote add origin https://github.com/operator-x17/REPO_NAME.git
```

### Error: "failed to push some refs"
```bash
# Pull first, then push
git pull origin main --allow-unrelated-histories
git push -u origin main
```

### Error: "Authentication failed"
Use Personal Access Token instead of password.

---

## ✅ Verify Push

After pushing, check:
1. Go to: https://github.com/operator-x17/REPO_NAME
2. Verify it's **PRIVATE** (lock icon)
3. Check all files are there
4. Verify `.env` is NOT there (secrets safe)

---

## 🎯 Repository Name Suggestions

- `zrai-lead-os` (recommended)
- `lead-intelligence-system`
- `bangalore-lead-machine`
- `clinic-lead-generator`

Choose one and replace `REPO_NAME` in commands above.

---

## 📝 Recommended Commit Message

```
ZRAI Lead OS v1.0 - Bangalore 500 Lead War Run

Complete autonomous lead generation system:
- LangGraph orchestration with 12-node pipeline
- OpenRouter + Kimi K2 LLM integration
- Apify Google Maps discovery
- Steel browser automation (ready)
- Firecrawl web scraping
- Supabase database with 15+ tables
- Revenue calculator + leak scoring
- Automated outreach generation
- Full frontend with Next.js

Target: ₹5L/month in 30 days
Status: Production ready
```

---

## 🚀 READY TO PUSH?

Run these commands in your terminal:

```bash
git add .
git commit -m "ZRAI Lead OS v1.0 - Complete system"
git remote add origin https://github.com/operator-x17/zrai-lead-os.git
git push -u origin main
```

**Done!** 🎉
