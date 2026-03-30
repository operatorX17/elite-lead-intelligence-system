import { z } from "zod";
import { auth } from "@/app/(auth)/auth";
import {
  getWhatsAppCampaignById,
  updateWhatsAppCampaign,
} from "@/lib/db/whatsapp-campaigns";

const updateCampaignSchema = z.object({
  status: z.enum(["draft", "active", "paused", "completed"]).optional(),
  messageTemplate: z.string().trim().min(1).optional(),
  templateName: z.string().trim().nullable().optional(),
  notes: z.string().trim().nullable().optional(),
  dailyLimit: z.coerce.number().int().min(1).max(500).optional(),
  waveSize: z.coerce.number().int().min(1).max(100).optional(),
  waveGapMinutes: z.coerce.number().int().min(1).max(240).optional(),
});

export async function GET(
  _request: Request,
  context: { params: Promise<{ id: string }> }
) {
  const session = await auth();
  if (!session?.user) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id } = await context.params;
  const campaign = await getWhatsAppCampaignById({ id });
  if (!campaign) {
    return Response.json({ error: "Campaign not found" }, { status: 404 });
  }

  return Response.json({ campaign });
}

export async function PATCH(
  request: Request,
  context: { params: Promise<{ id: string }> }
) {
  const session = await auth();
  if (!session?.user) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const rawBody = await request.json().catch(() => null);
  const payload = updateCampaignSchema.safeParse(rawBody);
  if (!payload.success) {
    return Response.json({ error: payload.error.flatten() }, { status: 400 });
  }

  const { id } = await context.params;
  const campaign = await updateWhatsAppCampaign({
    id,
    patch: payload.data,
  });

  if (!campaign) {
    return Response.json({ error: "Campaign not found" }, { status: 404 });
  }

  return Response.json({ campaign });
}
