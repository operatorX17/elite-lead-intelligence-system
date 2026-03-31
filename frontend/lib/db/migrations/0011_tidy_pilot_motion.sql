ALTER TABLE "WhatsAppConversation"
ADD COLUMN "opsState" jsonb DEFAULT '{}'::jsonb NOT NULL;
