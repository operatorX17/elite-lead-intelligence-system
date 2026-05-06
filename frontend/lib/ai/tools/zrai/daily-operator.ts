import { tool, type UIMessageStreamWriter } from "ai";
import { z } from "zod";
import type { ChatMessage } from "@/lib/types";
import { MAX_DISCOVERY_LIMIT, ZRAI_BACKEND_ENDPOINTS } from "@/lib/zrai/constants";
import { createZRAIProgressReporter } from "./progress";

type DiscoveredLead = {
  id?: string;
  company_name?: string;
  website?: string;
  phone?: string;
  email?: string;
  score?: number;
  geo?: string;
  niche?: string;
  source?: string;
  source_label?: string;
  status?: string;
};

function normalizeDailyNiche(niche: string) {
  const normalized = niche.trim().toLowerCase();
  if (
    normalized.includes("aesthetic") ||
    normalized.includes("skin") ||
    normalized.includes("laser") ||
    normalized.includes("hair") ||
    normalized.includes("clinic")
  ) {
    return "aesthetic clinic";
  }

  return niche.trim();
}

function buildLeadListArtifactData({
  geo,
  leads,
  niche,
  operatorBrief,
}: {
  geo: string;
  leads: DiscoveredLead[];
  niche: string;
  operatorBrief: Record<string, unknown>;
}) {
  return {
    autoAnalyzeCompletedToken: null,
    autoAnalyzeEnabled: true,
    dailyOperator: operatorBrief,
    geo,
    leads,
    niche,
    selectedLeadId: leads[0]?.id || null,
    sortBy: "score",
    sortOrder: "desc",
  };
}

function buildOperatorBrief({
  geo,
  leads,
  niche,
  ticket,
}: {
  geo: string;
  leads: DiscoveredLead[];
  niche: string;
  ticket: string;
}) {
  const topLeads = leads.slice(0, 5).map((lead, index) => ({
    rank: index + 1,
    company: lead.company_name || "Unnamed lead",
    contact_ready: Boolean(lead.phone || lead.email),
    score: lead.score ?? null,
    source: lead.source_label || lead.source || "discovery",
    website: lead.website || null,
  }));

  return {
    mode: "daily_operator",
    generated_at: new Date().toISOString(),
    geo,
    niche,
    ticket,
    lead_count: leads.length,
    operating_rule:
      "Use the canvas as the source of truth. Auto-analysis verifies facts before outreach. Send only after review.",
    today_sequence: [
      "Review all visible analyzed leads in the canvas.",
      "Draft outreach for the top 3 contact-ready leads.",
      "Send only approved messages.",
      "Log replies and follow up the same day.",
    ],
    follow_up_cadence: [
      "Day 0: first message with one specific observation.",
      "Day 2: short proof-based follow-up.",
      "Day 5: value-first bump with one operational idea.",
      "Day 10: close-loop message.",
    ],
    top_leads: topLeads,
  };
}

export const dailyOperator = ({
  dataStream,
}: {
  dataStream: UIMessageStreamWriter<ChatMessage>;
}) =>
  tool({
    description: `Run the ZRAI daily operator workflow for a solo founder.
Use this when the user wants a concrete daily lead engine, operator mode, traction, outreach, follow-up, or a "daily driver" workflow.
It discovers a focused lead batch, opens the lead-list canvas, enables automatic analysis, and returns the daily outreach operating brief.`,
    inputSchema: z.object({
      niche: z
        .string()
        .optional()
        .default("aesthetic clinic")
        .describe("Target niche. Default to aesthetic clinic unless the user asks for another market."),
      geo: z
        .string()
        .optional()
        .default("Bangalore")
        .describe("Target geography. Preserve the user's city/region exactly when provided."),
      limit: z
        .number()
        .min(1)
        .max(MAX_DISCOVERY_LIMIT)
        .optional()
        .default(5)
        .describe("Number of leads to discover. Default 5 for daily operator mode."),
      ticket: z
        .enum(["high_ticket", "mid_ticket", "any_ticket"])
        .optional()
        .default("any_ticket")
        .describe("Commercial targeting posture for outreach prioritization."),
      mock: z
        .boolean()
        .optional()
        .default(false)
        .describe("Use mock data only when the user explicitly requests a test run."),
    }),
    execute: async ({ niche, geo, limit, ticket, mock }) => {
      const progress = createZRAIProgressReporter({
        dataStream,
        tool: "dailyOperator",
        title: "Starting daily operator mode",
        stages: [
          "Set target",
          "Discover leads",
          "Open operator canvas",
          "Prepare outreach brief",
        ],
      });
      const normalizedNiche = normalizeDailyNiche(niche);

      progress.start(`Setting daily target: ${limit} ${normalizedNiche} leads in ${geo}.`, {
        geo,
        limit,
        niche: normalizedNiche,
      });

      try {
        progress.advance(1, "Running live discovery for the daily batch.");
        const response = await fetch(ZRAI_BACKEND_ENDPOINTS.discover, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            geo,
            limit,
            mock,
            niche: normalizedNiche,
          }),
        });

        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
          const detail =
            payload?.detail ||
            payload?.error?.message ||
            payload?.error ||
            `Discovery failed with status ${response.status}`;
          progress.error(1, String(detail), { status: response.status });
          return {
            success: false,
            error: String(detail),
            suggestion:
              "Use a narrower niche/city or run governance before retrying. Do not switch to mock data unless you want a test run.",
          };
        }

        const leads = Array.isArray(payload.leads)
          ? (payload.leads as DiscoveredLead[])
          : [];
        const operatorBrief = buildOperatorBrief({
          geo,
          leads,
          niche: normalizedNiche,
          ticket,
        });

        progress.advance(2, `Prepared ${leads.length} leads for the operator canvas.`, {
          discovered: leads.length,
        });
        progress.advance(3, "Prepared the daily outreach and follow-up operating brief.");
        progress.success("Daily operator mode is ready.", {
          discovered: leads.length,
        });

        return {
          success: true,
          count: leads.length,
          leads,
          operatorBrief,
          run_id: payload.run_id ?? null,
          summary:
            leads.length > 0
              ? `Daily operator mode is ready: ${leads.length} ${normalizedNiche} leads in ${geo}. The canvas will auto-analyze the visible leads; review the top leads, draft outreach for the contact-ready ones, and follow up on the cadence.`
              : `Daily operator mode ran for ${normalizedNiche} in ${geo}, but no live leads matched this pass.`,
          artifactTrigger: {
            kind: "lead-list" as const,
            data: buildLeadListArtifactData({
              geo,
              leads,
              niche: normalizedNiche,
              operatorBrief,
            }),
          },
        };
      } catch (error) {
        progress.error(
          1,
          error instanceof Error ? error.message : "Daily operator run failed"
        );
        return {
          success: false,
          error: error instanceof Error ? error.message : "Daily operator run failed",
          suggestion:
            "Check backend health and API credentials, then rerun daily operator mode with the same target.",
        };
      }
    },
  });
