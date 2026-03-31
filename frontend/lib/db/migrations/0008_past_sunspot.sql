CREATE TABLE IF NOT EXISTS "WhatsAppConversation" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"createdAt" timestamp NOT NULL,
	"updatedAt" timestamp NOT NULL,
	"contactName" text NOT NULL,
	"contactPhone" varchar(32) NOT NULL,
	"mode" varchar DEFAULT 'bot' NOT NULL,
	"status" varchar DEFAULT 'open' NOT NULL,
	"unreadCount" integer DEFAULT 0 NOT NULL,
	"lastMessagePreview" text DEFAULT '' NOT NULL,
	"lastMessageAt" timestamp NOT NULL,
	"source" varchar DEFAULT 'manual' NOT NULL,
	"assignedOperatorLabel" text
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "WhatsAppMessage" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"conversationId" uuid NOT NULL,
	"direction" varchar NOT NULL,
	"authorType" varchar DEFAULT 'contact' NOT NULL,
	"authorLabel" text NOT NULL,
	"body" text NOT NULL,
	"providerMessageId" text,
	"status" varchar DEFAULT 'draft' NOT NULL,
	"errorText" text,
	"createdAt" timestamp NOT NULL
);
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "WhatsAppMessage" ADD CONSTRAINT "WhatsAppMessage_conversationId_WhatsAppConversation_id_fk" FOREIGN KEY ("conversationId") REFERENCES "public"."WhatsAppConversation"("id") ON DELETE no action ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
CREATE UNIQUE INDEX IF NOT EXISTS "whatsapp_contact_phone_idx" ON "WhatsAppConversation" USING btree ("contactPhone");