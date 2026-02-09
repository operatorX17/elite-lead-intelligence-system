// Setup database tables using Supabase REST API
import 'dotenv/config';

const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;

if (!SUPABASE_URL || !SUPABASE_SERVICE_KEY) {
  console.error('❌ Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in .env.local');
  process.exit(1);
}

// SQL statements to create tables (one at a time for better error handling)
const statements = [
  // 1. User table
  `CREATE TABLE IF NOT EXISTS "User" (
    "id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
    "email" varchar(64) NOT NULL,
    "password" varchar(64)
  )`,
  
  // 2. Chat table
  `CREATE TABLE IF NOT EXISTS "Chat" (
    "id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
    "createdAt" timestamp NOT NULL,
    "title" text NOT NULL,
    "userId" uuid NOT NULL,
    "visibility" varchar DEFAULT 'private' NOT NULL,
    "lastContext" jsonb
  )`,
  
  // 3. Chat foreign key
  `DO $$ BEGIN
    ALTER TABLE "Chat" ADD CONSTRAINT "Chat_userId_User_id_fk" 
    FOREIGN KEY ("userId") REFERENCES "public"."User"("id") ON DELETE no action ON UPDATE no action;
  EXCEPTION WHEN duplicate_object THEN null; END $$`,
  
  // 4. Document table
  `CREATE TABLE IF NOT EXISTS "Document" (
    "id" uuid DEFAULT gen_random_uuid() NOT NULL,
    "createdAt" timestamp NOT NULL,
    "title" text NOT NULL,
    "content" text,
    "text" varchar DEFAULT 'text' NOT NULL,
    "userId" uuid NOT NULL,
    CONSTRAINT "Document_id_createdAt_pk" PRIMARY KEY("id","createdAt")
  )`,
  
  // 5. Document foreign key
  `DO $$ BEGIN
    ALTER TABLE "Document" ADD CONSTRAINT "Document_userId_User_id_fk" 
    FOREIGN KEY ("userId") REFERENCES "public"."User"("id") ON DELETE no action ON UPDATE no action;
  EXCEPTION WHEN duplicate_object THEN null; END $$`,
  
  // 6. Suggestion table
  `CREATE TABLE IF NOT EXISTS "Suggestion" (
    "id" uuid DEFAULT gen_random_uuid() NOT NULL,
    "documentId" uuid NOT NULL,
    "documentCreatedAt" timestamp NOT NULL,
    "originalText" text NOT NULL,
    "suggestedText" text NOT NULL,
    "description" text,
    "isResolved" boolean DEFAULT false NOT NULL,
    "userId" uuid NOT NULL,
    "createdAt" timestamp NOT NULL,
    CONSTRAINT "Suggestion_id_pk" PRIMARY KEY("id")
  )`,
  
  // 7. Suggestion foreign keys
  `DO $$ BEGIN
    ALTER TABLE "Suggestion" ADD CONSTRAINT "Suggestion_userId_User_id_fk" 
    FOREIGN KEY ("userId") REFERENCES "public"."User"("id") ON DELETE no action ON UPDATE no action;
  EXCEPTION WHEN duplicate_object THEN null; END $$`,
  
  `DO $$ BEGIN
    ALTER TABLE "Suggestion" ADD CONSTRAINT "Suggestion_documentId_documentCreatedAt_Document_id_createdAt_fk" 
    FOREIGN KEY ("documentId","documentCreatedAt") REFERENCES "public"."Document"("id","createdAt") ON DELETE no action ON UPDATE no action;
  EXCEPTION WHEN duplicate_object THEN null; END $$`,
  
  // 8. Message table (v1 deprecated)
  `CREATE TABLE IF NOT EXISTS "Message" (
    "id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
    "chatId" uuid NOT NULL,
    "role" varchar NOT NULL,
    "content" json NOT NULL,
    "createdAt" timestamp NOT NULL
  )`,
  
  // 9. Message foreign key
  `DO $$ BEGIN
    ALTER TABLE "Message" ADD CONSTRAINT "Message_chatId_Chat_id_fk" 
    FOREIGN KEY ("chatId") REFERENCES "public"."Chat"("id") ON DELETE no action ON UPDATE no action;
  EXCEPTION WHEN duplicate_object THEN null; END $$`,
  
  // 10. Vote table (v1 deprecated)
  `CREATE TABLE IF NOT EXISTS "Vote" (
    "chatId" uuid NOT NULL,
    "messageId" uuid NOT NULL,
    "isUpvoted" boolean NOT NULL,
    CONSTRAINT "Vote_chatId_messageId_pk" PRIMARY KEY("chatId","messageId")
  )`,
  
  // 11. Vote foreign keys
  `DO $$ BEGIN
    ALTER TABLE "Vote" ADD CONSTRAINT "Vote_chatId_Chat_id_fk" 
    FOREIGN KEY ("chatId") REFERENCES "public"."Chat"("id") ON DELETE no action ON UPDATE no action;
  EXCEPTION WHEN duplicate_object THEN null; END $$`,
  
  `DO $$ BEGIN
    ALTER TABLE "Vote" ADD CONSTRAINT "Vote_messageId_Message_id_fk" 
    FOREIGN KEY ("messageId") REFERENCES "public"."Message"("id") ON DELETE no action ON UPDATE no action;
  EXCEPTION WHEN duplicate_object THEN null; END $$`,
  
  // 12. Message_v2 table (current)
  `CREATE TABLE IF NOT EXISTS "Message_v2" (
    "id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
    "chatId" uuid NOT NULL,
    "role" varchar NOT NULL,
    "parts" json NOT NULL,
    "attachments" json NOT NULL,
    "createdAt" timestamp NOT NULL
  )`,
  
  // 13. Message_v2 foreign key
  `DO $$ BEGIN
    ALTER TABLE "Message_v2" ADD CONSTRAINT "Message_v2_chatId_Chat_id_fk" 
    FOREIGN KEY ("chatId") REFERENCES "public"."Chat"("id") ON DELETE no action ON UPDATE no action;
  EXCEPTION WHEN duplicate_object THEN null; END $$`,
  
  // 14. Vote_v2 table (current)
  `CREATE TABLE IF NOT EXISTS "Vote_v2" (
    "chatId" uuid NOT NULL,
    "messageId" uuid NOT NULL,
    "isUpvoted" boolean NOT NULL,
    CONSTRAINT "Vote_v2_chatId_messageId_pk" PRIMARY KEY("chatId","messageId")
  )`,
  
  // 15. Vote_v2 foreign keys
  `DO $$ BEGIN
    ALTER TABLE "Vote_v2" ADD CONSTRAINT "Vote_v2_chatId_Chat_id_fk" 
    FOREIGN KEY ("chatId") REFERENCES "public"."Chat"("id") ON DELETE no action ON UPDATE no action;
  EXCEPTION WHEN duplicate_object THEN null; END $$`,
  
  `DO $$ BEGIN
    ALTER TABLE "Vote_v2" ADD CONSTRAINT "Vote_v2_messageId_Message_v2_id_fk" 
    FOREIGN KEY ("messageId") REFERENCES "public"."Message_v2"("id") ON DELETE no action ON UPDATE no action;
  EXCEPTION WHEN duplicate_object THEN null; END $$`,
  
  // 16. Stream table
  `CREATE TABLE IF NOT EXISTS "Stream" (
    "id" uuid DEFAULT gen_random_uuid() NOT NULL,
    "chatId" uuid NOT NULL,
    "createdAt" timestamp NOT NULL,
    CONSTRAINT "Stream_id_pk" PRIMARY KEY("id")
  )`,
  
  // 17. Stream foreign key
  `DO $$ BEGIN
    ALTER TABLE "Stream" ADD CONSTRAINT "Stream_chatId_Chat_id_fk" 
    FOREIGN KEY ("chatId") REFERENCES "public"."Chat"("id") ON DELETE no action ON UPDATE no action;
  EXCEPTION WHEN duplicate_object THEN null; END $$`,
];

async function runSQL(sql) {
  const response = await fetch(`${SUPABASE_URL}/rest/v1/rpc/exec_sql`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'apikey': SUPABASE_SERVICE_KEY,
      'Authorization': `Bearer ${SUPABASE_SERVICE_KEY}`,
    },
    body: JSON.stringify({ sql }),
  });
  
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`HTTP ${response.status}: ${text}`);
  }
  
  return response.json();
}

async function main() {
  console.log('🚀 ZRAI Lead OS - Database Setup');
  console.log('================================');
  console.log(`Supabase URL: ${SUPABASE_URL}`);
  console.log('');
  
  // The Supabase REST API doesn't support raw SQL execution
  // We need to use the SQL Editor in the dashboard
  console.log('❌ Cannot run raw SQL via REST API.');
  console.log('');
  console.log('📋 Please run the migration manually:');
  console.log('');
  console.log('1. Open: https://supabase.com/dashboard/project/qjjvmoltqkfrfmipayte/sql/new');
  console.log('2. Copy the contents of: frontend/SUPABASE_MIGRATION.sql');
  console.log('3. Paste into the SQL Editor');
  console.log('4. Click "Run"');
  console.log('');
  console.log('After running the migration, restart the dev server:');
  console.log('  npm run dev');
}

main();
