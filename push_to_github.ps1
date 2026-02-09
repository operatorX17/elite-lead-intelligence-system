# Push to operator-x17 GitHub account as private repo

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "PUSHING TO OPERATOR-X17 GITHUB" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Add all changes
Write-Host "Step 1: Adding all changes..." -ForegroundColor Yellow
git add .

# Step 2: Commit
Write-Host "Step 2: Committing changes..." -ForegroundColor Yellow
git commit -m "ZRAI Lead OS v1.0 - Scoring fix complete (55+ HOT threshold)"

# Step 3: Remove old remote if exists
Write-Host "Step 3: Setting up remote..." -ForegroundColor Yellow
git remote remove origin 2>$null
git remote add origin https://github.com/operator-x17/zrai-lead-os.git

# Step 4: Set branch to main
Write-Host "Step 4: Setting branch to main..." -ForegroundColor Yellow
git branch -M main

# Step 5: Push
Write-Host "Step 5: Pushing to GitHub..." -ForegroundColor Yellow
Write-Host ""
Write-Host "⚠️  You will be prompted for GitHub credentials:" -ForegroundColor Red
Write-Host "   Username: operator-x17" -ForegroundColor White
Write-Host "   Password: [Use Personal Access Token]" -ForegroundColor White
Write-Host ""
Write-Host "Generate token at: https://github.com/settings/tokens" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press any key to continue..." -ForegroundColor Yellow
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

git push -u origin main --force

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "✅ PUSH COMPLETE!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Repository: https://github.com/operator-x17/zrai-lead-os" -ForegroundColor Cyan
Write-Host "Visibility: Private ✅" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Go to: https://github.com/operator-x17/zrai-lead-os"
Write-Host "2. Verify it shows 'Private' badge"
Write-Host "3. Check that .env is NOT visible"
Write-Host "4. Add collaborators if needed"
Write-Host ""
