ALTER TABLE "WhatsAppConversation" ADD COLUMN "linkedLeadId" text;--> statement-breakpoint
ALTER TABLE "WhatsAppConversation" ADD COLUMN "backendConversationId" text;--> statement-breakpoint
ALTER TABLE "WhatsAppConversation" ADD COLUMN "leadContext" jsonb;