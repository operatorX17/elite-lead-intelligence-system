#!/bin/bash
# Push to operator-x17 GitHub account as private repo

echo "=========================================="
echo "PUSHING TO OPERATOR-X17 GITHUB"
echo "=========================================="
echo ""

# Step 1: Add all changes
echo "Step 1: Adding all changes..."
git add .

# Step 2: Commit
echo "Step 2: Committing changes..."
git commit -m "ZRAI Lead OS v1.0 - Scoring fix complete (55+ HOT threshold)"

# Step 3: Remove old remote if exists
echo "Step 3: Setting up remote..."
git remote remove origin 2>/dev/null || true
git remote add origin https://github.com/operator-x17/zrai-lead-os.git

# Step 4: Set branch to main
echo "Step 4: Setting branch to main..."
git branch -M main

# Step 5: Push
echo "Step 5: Pushing to GitHub..."
echo ""
echo "⚠️  You will be prompted for GitHub credentials:"
echo "   Username: operator-x17"
echo "   Password: [Use Personal Access Token]"
echo ""
echo "Generate token at: https://github.com/settings/tokens"
echo ""

git push -u origin main --force

echo ""
echo "=========================================="
echo "✅ PUSH COMPLETE!"
echo "=========================================="
echo ""
echo "Repository: https://github.com/operator-x17/zrai-lead-os"
echo "Visibility: Private ✅"
echo ""
echo "Next steps:"
echo "1. Go to: https://github.com/operator-x17/zrai-lead-os"
echo "2. Verify it shows 'Private' badge"
echo "3. Check that .env is NOT visible"
echo "4. Add collaborators if needed"
echo ""
