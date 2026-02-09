# Supabase Setup Guide for ZRAI Lead OS

## Step 1: Create a Supabase Project

1. Go to [https://supabase.com](https://supabase.com)
2. Sign in or create an account
3. Click "New Project"
4. Fill in:
   - **Organization**: Select or create one
   - **Project name**: `zrai-lead-os`
   - **Database Password**: Generate a strong password (SAVE THIS!)
   - **Region**: Choose closest to you (e.g., `us-east-1`)
5. Click "Create new project"
6. Wait 2-3 minutes for project to be ready

---

## Step 2: Get Your API Keys

Once your project is ready:

1. Go to **Project Settings** (gear icon in sidebar)
2. Click **API** in the left menu
3. Copy these values:

| Setting | Where to find | Example |
|---------|---------------|---------|
| **Project URL** | Under "Project URL" | `https://abcdefghijk.supabase.co` |
| **anon public** | Under "Project API keys" | `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` |
| **service_role** | Under "Project API keys" (click "Reveal") | `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` |

4. Go to **Database** → **Connection string**
5. Select "URI" and copy the connection string
   - Replace `[YOUR-PASSWORD]` with your database password

---

## Step 3: Update Your .env File

Open your `.env` file and update these values:

```bash
# DATABASE (Supabase)
SUPABASE_URL=https://YOUR-PROJECT-ID.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...your-anon-key
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...your-service-role-key
DATABASE_URL=postgresql://postgres:YOUR-PASSWORD@db.YOUR-PROJECT-ID.supabase.co:5432/postgres
```

---

## Step 4: Run Database Migrations

### Option A: Using Supabase SQL Editor (Recommended)

1. Go to your Supabase Dashboard
2. Click **SQL Editor** in the sidebar
3. Click **New query**
4. Copy the ENTIRE contents of `migrations/001_initial_schema.sql`
5. Paste into the SQL Editor
6. Click **Run** (or press Ctrl+Enter)
7. You should see "Success. No rows returned"

### Option B: Using psql (Command Line)

```bash
# Install psql if not installed
# Windows: Download from https://www.postgresql.org/download/windows/

# Run migration
psql "postgresql://postgres:YOUR-PASSWORD@db.YOUR-PROJECT-ID.supabase.co:5432/postgres" -f migrations/001_initial_schema.sql
```

---

## Step 5: Enable Vector Extension (for Playbooks)

In the SQL Editor, run:

```sql
-- Enable pgvector for playbook embeddings
CREATE EXTENSION IF NOT EXISTS vector;
```

---

## Step 6: Verify Setup

### Check Tables Were Created

In SQL Editor, run:

```sql
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
ORDER BY table_name;
```

You should see these tables:
- `ab_metrics`
- `ab_tests`
- `audit_log`
- `circuit_breakers`
- `conversations`
- `daily_metrics`
- `do_not_contact`
- `enrichment_data`
- `escalations`
- `golden_dataset`
- `intent_data`
- `lead_state`
- `leads`
- `negative_signals`
- `outreach_queue`
- `playbooks`
- `proof_artifacts`
- `scoring_results`
- `usage_metrics`

### Test Connection from Python

Run this test script:

```bash
python test_supabase_connection.py
```

---

## Step 7: Create Storage Bucket (Optional)

If using Supabase Storage for screenshots:

1. Go to **Storage** in sidebar
2. Click **New bucket**
3. Name: `zrai-artifacts`
4. Make it **Public** (for screenshot URLs)
5. Click **Create bucket**

---

## Troubleshooting

### "relation does not exist" error
- Make sure you ran the migration SQL
- Check you're connected to the right project

### "permission denied" error
- Make sure you're using the `service_role` key, not `anon` key
- Check RLS policies aren't blocking access

### Connection timeout
- Check your IP isn't blocked (Supabase Dashboard → Database → Connection Pooling)
- Try using the pooler connection string instead

### Vector extension error
- Run `CREATE EXTENSION IF NOT EXISTS vector;` first
- Some Supabase plans may not support pgvector

---

## Quick Reference

After setup, your `.env` should look like:

```bash
SUPABASE_URL=https://abcdefghijk.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFiY2RlZmdoaWprIiwicm9sZSI6ImFub24iLCJpYXQiOjE2...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFiY2RlZmdoaWprIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTY...
DATABASE_URL=postgresql://postgres:MySecurePassword123@db.abcdefghijk.supabase.co:5432/postgres
```

---

## Next Steps

After Supabase is set up:

1. Run `python test_supabase_connection.py` to verify
2. Run `python -m src.cli status` to check system status
3. Run `python -m src.cli dry_run --limit 1` to test the pipeline

---

*Need help? Check the Supabase docs at https://supabase.com/docs*
