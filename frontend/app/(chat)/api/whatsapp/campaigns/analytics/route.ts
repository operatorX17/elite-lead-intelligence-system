import { auth } from "@/app/(auth)/auth";
import { listWhatsAppCampaigns } from "@/lib/db/whatsapp-campaigns";
import { listWhatsAppConversations } from "@/lib/db/queries";
import { computeWhatsAppCampaignAnalytics } from "@/lib/whatsapp/campaign-analytics";

export async function GET() {
  const session = await auth();
  if (!session?.user) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const [campaigns, conversations] = await Promise.all([
    listWhatsAppCampaigns(),
    listWhatsAppConversations(),
  ]);

  const analytics = computeWhatsAppCampaignAnalytics({
    campaigns,
    conversations,
  });

  return Response.json({ analytics });
}
