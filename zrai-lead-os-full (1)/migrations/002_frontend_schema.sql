-- ============================================
-- ZRAI Lead OS - Frontend Schema Migration
-- For Vercel AI Chat SDK (Next.js frontend)
-- ============================================

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- User Table (for auth)
-- ============================================
CREATE TABLE IF NOT EXISTS "User" (
    "id" UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    "email" VARCHAR(64) NOT NULL,
    "password" VARCHAR(64)
);

-- ============================================
-- Chat Table
-- ============================================
CREATE TABLE IF NOT EXISTS "Chat" (
    "id" UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    "createdAt" TIMESTAMP NOT NULL,
    "title" TEXT NOT NULL,
    "userId" UUID NOT NULL REFERENCES "User"("id") ON DELETE CASCADE,
    "visibility" VARCHAR(10) NOT NULL DEFAULT 'private' CHECK ("visibility" IN ('public', 'private'))
);

-- Index for faster user chat lookups
CREATE INDEX IF NOT EXISTS "idx_chat_userId" ON "Chat"("userId");

-- ============================================
-- Message Table (deprecated - for backwards compatibility)
-- ============================================
CREATE TABLE IF NOT EXISTS "Message" (
    "id" UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    "chatId" UUID NOT NULL REFERENCES "Chat"("id") ON DELETE CASCADE,
    "role" VARCHAR(50) NOT NULL,
    "content" JSONB NOT NULL,
    "createdAt" TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS "idx_message_chatId" ON "Message"("chatId");

-- ============================================
-- Message_v2 Table (current version)
-- ============================================
CREATE TABLE IF NOT EXISTS "Message_v2" (
    "id" UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    "chatId" UUID NOT NULL REFERENCES "Chat"("id") ON DELETE CASCADE,
    "role" VARCHAR(50) NOT NULL,
    "parts" JSONB NOT NULL,
    "attachments" JSONB NOT NULL,
    "createdAt" TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS "idx_message_v2_chatId" ON "Message_v2"("chatId");

-- ============================================
-- Vote Table (deprecated - for backwards compatibility)
-- ============================================
CREATE TABLE IF NOT EXISTS "Vote" (
    "chatId" UUID NOT NULL REFERENCES "Chat"("id") ON DELETE CASCADE,
    "messageId" UUID NOT NULL REFERENCES "Message"("id") ON DELETE CASCADE,
    "isUpvoted" BOOLEAN NOT NULL,
    PRIMARY KEY ("chatId", "messageId")
);

-- ============================================
-- Vote_v2 Table (current version)
-- ============================================
CREATE TABLE IF NOT EXISTS "Vote_v2" (
    "chatId" UUID NOT NULL REFERENCES "Chat"("id") ON DELETE CASCADE,
    "messageId" UUID NOT NULL REFERENCES "Message_v2"("id") ON DELETE CASCADE,
    "isUpvoted" BOOLEAN NOT NULL,
    PRIMARY KEY ("chatId", "messageId")
);

-- ============================================
-- Document Table (for artifacts/documents)
-- ============================================
CREATE TABLE IF NOT EXISTS "Document" (
    "id" UUID NOT NULL DEFAULT uuid_generate_v4(),
    "createdAt" TIMESTAMP NOT NULL,
    "title" TEXT NOT NULL,
    "content" TEXT,
    "kind" VARCHAR(50) NOT NULL DEFAULT 'text' CHECK ("kind" IN (
        'text', 
        'code', 
        'image', 
        'sheet',
        'lead-card',
        'lead-list',
        'proof-viewer',
        'scoring-dashboard',
        'outreach-draft',
        'conversation-thread',
        'metrics-dashboard',
        'lead-sheet'
    )),
    "userId" UUID NOT NULL REFERENCES "User"("id") ON DELETE CASCADE,
    PRIMARY KEY ("id", "createdAt")
);

CREATE INDEX IF NOT EXISTS "idx_document_userId" ON "Document"("userId");

-- ============================================
-- Suggestion Table
-- ============================================
CREATE TABLE IF NOT EXISTS "Suggestion" (
    "id" UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    "documentId" UUID NOT NULL,
    "documentCreatedAt" TIMESTAMP NOT NULL,
    "originalText" TEXT NOT NULL,
    "suggestedText" TEXT NOT NULL,
    "description" TEXT,
    "isResolved" BOOLEAN NOT NULL DEFAULT FALSE,
    "userId" UUID NOT NULL REFERENCES "User"("id") ON DELETE CASCADE,
    "createdAt" TIMESTAMP NOT NULL,
    FOREIGN KEY ("documentId", "documentCreatedAt") REFERENCES "Document"("id", "createdAt") ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS "idx_suggestion_userId" ON "Suggestion"("userId");

-- ============================================
-- Stream Table (for streaming responses)
-- ============================================
CREATE TABLE IF NOT EXISTS "Stream" (
    "id" UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    "chatId" UUID NOT NULL REFERENCES "Chat"("id") ON DELETE CASCADE,
    "createdAt" TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS "idx_stream_chatId" ON "Stream"("chatId");

-- ============================================
-- Grant permissions (for Supabase)
-- ============================================
GRANT ALL ON "User" TO postgres, anon, authenticated, service_role;
GRANT ALL ON "Chat" TO postgres, anon, authenticated, service_role;
GRANT ALL ON "Message" TO postgres, anon, authenticated, service_role;
GRANT ALL ON "Message_v2" TO postgres, anon, authenticated, service_role;
GRANT ALL ON "Vote" TO postgres, anon, authenticated, service_role;
GRANT ALL ON "Vote_v2" TO postgres, anon, authenticated, service_role;
GRANT ALL ON "Document" TO postgres, anon, authenticated, service_role;
GRANT ALL ON "Suggestion" TO postgres, anon, authenticated, service_role;
GRANT ALL ON "Stream" TO postgres, anon, authenticated, service_role;
