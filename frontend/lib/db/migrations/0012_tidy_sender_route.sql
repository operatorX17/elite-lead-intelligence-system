ALTER TABLE "WhatsAppConversation"
ADD COLUMN "businessPhone" varchar(32) DEFAULT '' NOT NULL;
--> statement-breakpoint
DROP INDEX IF EXISTS "whatsapp_contact_phone_idx";
--> statement-breakpoint
CREATE UNIQUE INDEX IF NOT EXISTS "whatsapp_contact_route_idx"
ON "WhatsAppConversation" USING btree ("contactPhone", "businessPhone");
