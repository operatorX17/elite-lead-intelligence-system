import { z } from "zod";
import { auth } from "@/app/(auth)/auth";
import {
  createWhatsAppCampaign,
  listWhatsAppCampaigns,
} from "@/lib/db/whatsapp-campaigns";
import { getWhatsAppConversationByPhone } from "@/lib/db/queries";
import {
  parseCampaignContactsInput,
  renderCampaignMessageTemplate,
} from "@/lib/whatsapp/campaigns";

const createCampaignSchema = z.object({
  name: z.string().trim().min(1, "Campaign name is required"),
  messageStyle: z.enum(["template", "freeform"]).default("template"),
  templateName: z.string().trim().optional(),
  messageTemplate: z.string().trim().min(1, "First message is required"),
  contactsText: z.string().trim().min(1, "At least one contact is required"),
  dailyLimit: z.coerce.number().int().min(1).max(500).default(20),
  waveSize: z.coerce.number().int().min(1).max(100).default(10),
  waveGapMinutes: z.coerce.number().int().min(1).max(240).default(30),
  notes: z.string().trim().optional(),
});

export async function GET() {
  const session = await auth();
  if (!session?.user) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const campaigns = await listWhatsAppCampaigns();
  return Response.json({ campaigns });
}

export async function POST(request: Request) {
  const session = await auth();
  if (!session?.user) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const rawBody = await request.json().catch(() => null);
  const payload = createCampaignSchema.safeParse(rawBody);

  if (!payload.success) {
    return Response.json({ error: payload.error.flatten() }, { status: 400 });
  }

  const contacts = parseCampaignContactsInput(payload.data.contactsText);
  if (contacts.length === 0) {
    return Response.json(
      { error: { formErrors: ["Could not parse any valid contacts"] } },
      { status: 400 }
    );
  }

  const enrichedRecipients = await Promise.all(
    contacts.map(async (recipient) => {
      const existingConversation = await getWhatsAppConversationByPhone({
        contactPhone: recipient.contactPhone,
      });
      const leadContext = existingConversation?.leadContext ?? null;

      return {
        ...recipient,
        linkedLeadId: existingConversation?.linkedLeadId ?? null,
        conversationId: existingConversation?.id ?? null,
        renderedBody: renderCampaignMessageTemplate({
          template: payload.data.messageTemplate,
          contactName: recipient.contactName,
          contactPhone: recipient.contactPhone,
          companyName: recipient.companyName ?? leadContext?.companyName ?? null,
          topIssue: leadContext?.topIssue ?? null,
          decisionMakerName: leadContext?.decisionMakerName ?? null,
          city: leadContext?.geo ?? null,
        }),
      };
    })
  );

  const campaign = await createWhatsAppCampaign({
    name: payload.data.name,
    messageStyle: payload.data.messageStyle,
    templateName: payload.data.templateName,
    messageTemplate: payload.data.messageTemplate,
    createdByLabel:
      session.user.email ?? session.user.name ?? "Human operator",
    dailyLimit: payload.data.dailyLimit,
    waveSize: payload.data.waveSize,
    waveGapMinutes: payload.data.waveGapMinutes,
    notes: payload.data.notes,
    recipients: enrichedRecipients,
  });

  return Response.json({ campaign });
}
