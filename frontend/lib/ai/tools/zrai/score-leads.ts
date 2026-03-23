/**
 * ZRAI Lead OS - Score Leads Tool
 *
 * Scores leads based on intent, fit, engagement, and recency.
 */

import { tool, type UIMessageStreamWriter } from "ai";
import { z } from "zod";
import type { ChatMessage } from "@/lib/types";
import { ZRAI_BACKEND_ENDPOINTS } from "@/lib/zrai/constants";
import { createZRAIProgressReporter } from "./progress";

export const scoreLeads = ({
  dataStream,
}: {
  dataStream: UIMessageStreamWriter<ChatMessage>;
}) =>
  tool({
    description: `Score leads based on intent, fit, engagement, and recency factors.
Use this tool to prioritize your pipeline and identify the most promising leads.
Returns ranked leads with detailed score breakdowns.`,
    inputSchema: z.object({
      niche: z
        .string()
        .optional()
        .describe('Filter by niche (e.g., "saas", "ecommerce")'),
      geo: z.string().optional().describe("Filter by geographic region"),
      min_score: z
        .number()
        .min(0)
        .max(100)
        .optional()
        .describe("Minimum score threshold (0-100)"),
      lead_ids: z
        .array(z.string().uuid())
        .optional()
        .describe(
          "Specific lead IDs to score (if not provided, scores all eligible leads)"
        ),
    }),
    execute: async ({ niche, geo, min_score, lead_ids }) => {
      const progress = createZRAIProgressReporter({
        dataStream,
        tool: "scoreLeads",
        title: "Scoring lead pipeline",
        stages: ["Select leads", "Run scoring", "Prepare ranking dashboard"],
      });
      progress.start("Selecting the lead set to score.", {
        geo: geo ?? null,
        leadCount: lead_ids?.length ?? null,
        minScore: min_score ?? null,
        niche: niche ?? null,
      });
      try {
        progress.advance(
          1,
          "Running scoring across fit, intent, engagement, and recency signals."
        );
        const response = await fetch(ZRAI_BACKEND_ENDPOINTS.score, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ niche, geo, min_score, lead_ids }),
        });

        const data = await response.json();

        if (!response.ok || !data.success) {
          progress.error(1, data.error?.message || "Failed to score leads", {
            status: response.status,
          });
          return {
            success: false,
            error: data.error?.message || "Failed to score leads",
            suggestion: "Try again or check if leads exist.",
          };
        }

        const count = data?.data?.count ?? data?.count ?? 0;
        const results = Array.isArray(data?.data?.results)
          ? data.data.results
          : Array.isArray(data?.results)
            ? data.results
            : [];
        const qualifiedCount = results.filter(
          (r: any) => !r.disqualified
        ).length;
        const topLead = results[0];
        const topLeadScore = topLead?.score_breakdown?.total_score ?? topLead?.lead?.score;
        progress.advance(
          2,
          `Preparing a ranked dashboard for ${count} scored lead${count === 1 ? "" : "s"}.`,
          { qualified: qualifiedCount, scored: count }
        );
        progress.success("Lead scoring is complete.", {
          qualified: qualifiedCount,
          topLead: topLead?.lead?.company_name ?? null,
        });

        return {
          success: true,
          results,
          count,
          summary: `Scored ${count} lead(s). ${qualifiedCount} qualified, ${count - qualifiedCount} disqualified. ${
            topLead
              ? `Top lead: ${topLead.lead.company_name} (score: ${topLeadScore ?? "n/a"})`
              : ""
          }`,
          artifactTrigger: {
            kind: "scoring-dashboard" as const,
            data: {
              results,
              count,
              scored_at: new Date().toISOString(),
            },
          },
        };
      } catch (error) {
        progress.error(
          1,
          error instanceof Error ? error.message : "Network error"
        );
        return {
          success: false,
          error: error instanceof Error ? error.message : "Network error",
          suggestion: "Please check your connection and try again.",
        };
      }
    },
  });
