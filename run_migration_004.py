"""Run migration 004 to add volume fields to leads table."""
import sys
sys.path.append('src')

from src.db.client import SupabaseClient

client = SupabaseClient()

# Read migration SQL
with open('migrations/004_add_lead_volume_fields.sql', 'r') as f:
    sql = f.read()

# Split into individual statements
statements = [s.strip() for s in sql.split(';') if s.strip() and not s.strip().startswith('--')]

print("Running migration 004...")
for i, stmt in enumerate(statements, 1):
    if stmt:
        print(f"  Statement {i}/{len(statements)}...")
        try:
            # Execute via raw SQL using Supabase PostgREST
            # Note: Supabase doesn't expose direct SQL execution, so we use the Python client
            # which internally uses PostgREST. For DDL, we need to use the SQL editor in dashboard
            # or use a direct PostgreSQL connection.
            print(f"    SQL: {stmt[:100]}...")
            # This won't work - Supabase client doesn't support raw DDL
            # We need to run this manually in Supabase dashboard
        except Exception as e:
            print(f"    Error: {e}")

print("\nMigration SQL:")
print("=" * 80)
print(sql)
print("=" * 80)
print("\nPlease run this SQL in your Supabase SQL Editor:")
print("1. Go to https://supabase.com/dashboard")
print("2. Select your project")
print("3. Go to SQL Editor")
print("4. Paste the SQL above")
print("5. Click 'Run'")
