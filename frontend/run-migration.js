// Run database migration using Supabase client
const { createClient } = require('@supabase/supabase-js');
require('dotenv').config({ path: '.env.local' });

const supabaseUrl = process.env.SUPABASE_URL;
const supabaseServiceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

if (!supabaseUrl || !supabaseServiceKey) {
  console.error('Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY');
  process.exit(1);
}

const supabase = createClient(supabaseUrl, supabaseServiceKey);

const migrationSQL = `
-- User table
CREATE TABLE IF NOT EXISTS "User" (
  "id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
  "email" varchar(64) NOT NULL,
  "password" varchar(64)
);

-- Chat table
CREATE TABLE IF NOT EXISTS "Chat" (
  "id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
  "createdAt" timestamp NOT NULL,
  "title" text NOT NULL,
  "userId" uuid NOT NULL REFERENCES "User"("id"),
  "visibility" varchar DEFAULT 'private' NOT NULL,
  "lastContext" jsonb
);

-- Document table
CREATE TABLE IF NOT EXISTS "Document" (
  "id" uuid DEFAULT gen_random_uuid() NOT NULL,
  "createdAt" timestamp NOT NULL,
  "title" text NOT NULL,
  "content" text,
  "text" varchar DEFAULT 'text' NOT NULL,
  "userId" uuid NOT NULL REFERENCES "User"("id"),
  CONSTRAINT "Document_id_createdAt_pk" PRIMARY KEY("id","createdAt")
);

-- Suggestion table
CREATE TABLE IF NOT EXISTS "Suggestion" (
  "id" uuid DEFAULT gen_random_uuid() NOT NULL,
  "documentId" uuid NOT NULL,
  "documentCreatedAt" timestamp NOT NULL,
  "originalText" text NOT NULL,
  "suggestedText" text NOT NULL,
  "description" text,
  "isResolved" boolean DEFAULT false NOT NULL,
  "userId" uuid NOT NULL REFERENCES "User"("id"),
  "createdAt" timestamp NOT NULL,
  CONSTRAINT "Suggestion_id_pk" PRIMARY KEY("id")
);

-- Message table (deprecated v1)
CREATE TABLE IF NOT EXISTS "Message" (
  "id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
  "chatId" uuid NOT NULL REFERENCES "Chat"("id"),
  "role" varchar NOT NULL,
  "content" json NOT NULL,
  "createdAt" timestamp NOT NULL
);

-- Vote table (deprecated v1)
CREATE TABLE IF NOT EXISTS "Vote" (
  "chatId" uuid NOT NULL REFERENCES "Chat"("id"),
  "messageId" uuid NOT NULL REFERENCES "Message"("id"),
  "isUpvoted" boolean NOT NULL,
  CONSTRAINT "Vote_chatId_messageId_pk" PRIMARY KEY("chatId","messageId")
);

-- Message_v2 table (current)
CREATE TABLE IF NOT EXISTS "Message_v2" (
  "id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
  "chatId" uuid NOT NULL REFERENCES "Chat"("id"),
  "role" varchar NOT NULL,
  "parts" json NOT NULL,
  "attachments" json NOT NULL,
  "createdAt" timestamp NOT NULL
);

-- Vote_v2 table (current)
CREATE TABLE IF NOT EXISTS "Vote_v2" (
  "chatId" uuid NOT NULL REFERENCES "Chat"("id"),
  "messageId" uuid NOT NULL REFERENCES "Message_v2"("id"),
  "isUpvoted" boolean NOT NULL,
  CONSTRAINT "Vote_v2_chatId_messageId_pk" PRIMARY KEY("chatId","messageId")
);

-- Stream table
CREATE TABLE IF NOT EXISTS "Stream" (
  "id" uuid DEFAULT gen_random_uuid() NOT NULL,
  "chatId" uuid NOT NULL REFERENCES "Chat"("id"),
  "createdAt" timestamp NOT NULL,
  CONSTRAINT "Stream_id_pk" PRIMARY KEY("id")
);
`;

async function runMigration() {
  console.log('⏳ Running migration via Supabase client...');
  
  try {
    const { data, error } = await supabase.rpc('exec_sql', { sql: migrationSQL });
    
    if (error) {
      // Try direct SQL execution via REST API
      console.log('RPC not available, trying alternative method...');
      
      // Split into individual statements and run each
      const statements = migrationSQL
        .split(';')
        .map(s => s.trim())
        .filter(s => s.length > 0 && !s.startsWith('--'));
      
      for (const stmt of statements) {
        console.log(`Running: ${stmt.substring(0, 50)}...`);
        // This won't work directly, but let's try
      }
      
      throw new Error('Cannot run raw SQL via Supabase client. Please run SUPABASE_MIGRATION.sql manually in the SQL Editor.');
    }
    
    console.log('✅ Migration completed!');
  } catch (err) {
    console.error('❌ Migration failed:', err.message);
    console.log('\\n📋 Please run the migration manually:');
    console.log('1. Go to: https://supabase.com/dashboard/project/qjjvmoltqkfrfmipayte/sql/new');
    console.log('2. Copy contents of frontend/SUPABASE_MIGRATION.sql');
    console.log('3. Paste and click "Run"');
    process.exit(1);
  }
}

runMigration();
