import { auth } from "@/app/(auth)/auth";
import { listWhatsAppCampaigns } from "@/lib/db/whatsapp-campaigns";
import { runWhatsAppCampaignWave } from "@/lib/whatsapp/campaign-runner";

function isCronAuthorized(request: Request) {
  const cronHeader = request.headers.get("x-vercel-cron");
  if (cronHeader) {
    return true;
  }

  const configuredSecret = process.env.CRON_SECRET?.trim();
  if (!configuredSecret) {
    return false;
  }

  const bearer = request.headers.get("authorization");
  if (bearer === `Bearer ${configuredSecret}`) {
    return true;
  }

  const url = new URL(request.url);
  return url.searchParams.get("secret") === configuredSecret;
}

export async function GET(request: Request) {
  const cronAuthorized = isCronAuthorized(request);
  const session = cronAuthorized ? null : await auth();

  if (!cronAuthorized && !session?.user) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const campaigns = await listWhatsAppCampaigns();
  const now = Date.now();
  const dueCampaigns = campaigns.filter((campaign) => {
    if (campaign.status !== "active") {
      return false;
    }

    const hasApprovedRecipients = campaign.recipients.some(
      (recipient) => recipient.status === "approved"
    );
    if (!hasApprovedRecipients) {
      return false;
    }

    if (!campaign.nextWaveAt) {
      return true;
    }

    return new Date(campaign.nextWaveAt).getTime() <= now;
  });

  const results = [];
  for (const campaign of dueCampaigns) {
    const result = await runWhatsAppCampaignWave({
      campaignId: campaign.id,
      operatorLabel: session?.user?.email ?? session?.user?.name ?? "Campaign scheduler",
      userId: session?.user?.id ?? null,
    });

    results.push({
      campaignId: campaign.id,
      campaignName: campaign.name,
      ok: !("error" in result),
      ...(result as object),
    });
  }

  return Response.json({
    checkedAt: new Date().toISOString(),
    dueCampaigns: dueCampaigns.length,
    dispatched: results.filter((result) => result.ok).length,
    results,
  });
}
