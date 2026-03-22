/**
 * ZRAI Lead OS - Analyze Intent Tool
 *
 * Analyzes intent signals and revenue leak indicators for a lead.
 */

import { tool, type UIMessageStreamWriter } from "ai";
import { z } from "zod";
import type { ChatMessage } from "@/lib/types";
import { ZRAI_BACKEND_ENDPOINTS } from "@/lib/zrai/constants";
import { createZRAIProgressReporter } from "./progress";

export const analyzeIntent = ({
  dataStream,
}: {
  dataStream: UIMessageStreamWriter<ChatMessage>;
}) =>
  tool({
    description: `Analyze a lead's intent signals and revenue leak indicators.
Use this tool to understand how likely a lead is to be interested in your offer based on their online behavior, tech stack, and business signals.
Returns intent signals with confidence scores and an overall revenue leak score.`,
    inputSchema: z.object({
      lead_id: z
        .string()
        .uuid()
        .describe("The unique identifier of the lead to analyze"),
    }),
    execute: async ({ lead_id }) => {
      const progress = createZRAIProgressReporter({
        dataStream,
        tool: "analyzeIntent",
        title: "Analyzing buying intent",
        stages: ["Load lead", "Score intent signals", "Prepare insight card"],
      });
      progress.start("Loading the lead context for intent analysis.", {
        leadId: lead_id,
      });
      try {
        progress.advance(
          1,
          "Running intent scoring across revenue leak and fit signals."
        );
        const response = await fetch(ZRAI_BACKEND_ENDPOINTS.intent, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ lead_id }),
        });

        const data = await response.json();

        if (!response.ok || !data.success) {
          progress.error(1, data.error?.message || "Failed to analyze intent", {
            status: response.status,
          });
          return {
            success: false,
            error: data.error?.message || "Failed to analyze intent",
            suggestion:
              data.error?.code === "not_found"
                ? "Lead not found. Please check the lead ID."
                : "Try again or enrich the lead first.",
          };
        }

        const { intent, lead } = data;
        const intent_signals = lead.intent_signals || [];
        const revenue_leak_score = intent?.leak_score || 0;
        const signalCount = intent_signals?.length || 0;
        const highConfidenceSignals =
          intent_signals?.filter((s: any) => s.confidence > 0.7) || [];
        progress.advance(
          2,
          `Preparing ${signalCount} intent signal${signalCount === 1 ? "" : "s"} and a leak score of ${revenue_leak_score}.`,
          { leakScore: revenue_leak_score, signals: signalCount }
        );
        progress.success(`Intent analysis complete for ${lead.company_name}.`, {
          highConfidenceSignals: highConfidenceSignals.length,
        });

        return {
          success: true,
          lead,
          intent_signals,
          revenue_leak_score,
          summary: `Found ${signalCount} intent signal(s) for ${lead.company_name}. Revenue leak score: ${revenue_leak_score}/100. ${
            highConfidenceSignals.length > 0
              ? `High-confidence signals: ${highConfidenceSignals.map((s: any) => s.signal_type).join(", ")}.`
              : "No high-confidence signals detected."
          }`,
          artifactTrigger: {
            kind: "lead-card" as const,
            data: lead,
          },
        };
      } catch (error) {
        progress.error(
          1,
          error instanceof Error ? error.message : "Network error",
          { leadId: lead_id }
        );
        return {
          success: false,
          error: error instanceof Error ? error.message : "Network error",
          suggestion: "Please check your connection and try again.",
        };
      }
    },
  });
