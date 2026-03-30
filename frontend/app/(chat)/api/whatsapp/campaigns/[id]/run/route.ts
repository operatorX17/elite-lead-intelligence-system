import { auth } from "@/app/(auth)/auth";
import { runWhatsAppCampaignWave } from "@/lib/whatsapp/campaign-runner";

export async function POST(
  _request: Request,
  context: { params: Promise<{ id: string }> }
) {
  const session = await auth();
  if (!session?.user) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id } = await context.params;
  const result = await runWhatsAppCampaignWave({
    campaignId: id,
    operatorLabel: session.user.email ?? session.user.name ?? "Human operator",
    userId: session.user.id,
  });

  if ("error" in result) {
    return Response.json(
      {
        error: result.error,
        nextWaveAt: "nextWaveAt" in result ? result.nextWaveAt : undefined,
      },
      { status: result.status }
    );
  }

  return Response.json({
    campaign: result.campaign,
    sentCount: result.sentCount,
    results: "results" in result ? result.results : undefined,
    blockedReason: "blockedReason" in result ? result.blockedReason : undefined,
  });
}
