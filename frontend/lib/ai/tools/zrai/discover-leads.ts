/**
 * ZRAI Lead OS - Discover Leads Tool
 *
 * Discovers leads based on niche and geo via the ZRAI Discovery Agent.
 */

import { tool, type UIMessageStreamWriter } from "ai";
import { z } from "zod";
import type { ChatMessage } from "@/lib/types";
import { MAX_DISCOVERY_LIMIT, ZRAI_BACKEND_URL } from "@/lib/zrai/constants";
import { createZRAIProgressReporter } from "./progress";

function normalizeClinicDiscoveryNiche(niche: string): string {
  const raw = String(niche || "").trim();
  const lowered = raw.toLowerCase();

  if (
    /(skin|aesthetic|derma|dermatology|cosmetic|medspa|beauty)/i.test(lowered)
  ) {
    return "premium skin and aesthetic clinics";
  }

  if (/(dental|dentist|orthodontic|oral)/i.test(lowered)) {
    return "premium dental clinics";
  }

  if (/(hair|transplant|trichology)/i.test(lowered)) {
    return "premium hair clinics";
  }

  return raw;
}

function isBudgetConstraint(detail: string | undefined): boolean {
  const message = String(detail || "").toLowerCase();
  return (
    message.includes("remaining usage") ||
    message.includes("billing/subscription") ||
    message.includes("budget exceeded") ||
    message.includes("paid plan")
  );
}

export const discoverLeads = ({
  dataStream,
}: {
  dataStream: UIMessageStreamWriter<ChatMessage>;
}) =>
  tool({
    description: `Discover new leads based on niche and geographic location. 
Use this tool when the user wants to find new prospects or leads in a specific industry or region.
Returns a list of discovered leads with basic company information.

NOTE: Discovery can take 2-5 minutes as it scrapes real data from Google Maps. 
Only set mock=true when the user explicitly asks for mock, fake, or test data.`,
    inputSchema: z.object({
      niche: z
        .string()
        .describe(
          'The industry niche to search for (e.g., "saas", "ecommerce", "agency", "fintech")'
        ),
      geo: z
        .string()
        .describe(
          'Geographic location to search. Preserve exact city names when the user gives one (e.g., "Bangalore", "Austin, Texas", "London"). Only use country or region codes like "us" or "uk" when the user asked for a country or region. Never omit this field.'
        ),
      limit: z
        .number()
        .min(1)
        .max(MAX_DISCOVERY_LIMIT)
        .optional()
        .default(20)
        .describe("Maximum number of leads to discover (1-200)"),
      mock: z
        .boolean()
        .optional()
        .default(false)
        .describe(
          "Use mock data for instant results only when the user explicitly requests test data"
        ),
    }),
    execute: async ({ niche, geo, limit, mock }) => {
      const normalizedNiche = normalizeClinicDiscoveryNiche(niche);
      console.log(
        `[discoverLeads] Starting discovery: niche=${niche}, normalizedNiche=${normalizedNiche}, geo=${geo}, limit=${limit}, mock=${mock}`
      );
      const progress = createZRAIProgressReporter({
        dataStream,
        tool: "discoverLeads",
        title: "Running discovery agent",
        stages: ["Parse request", "Fetch live leads", "Prepare lead artifact"],
      });
      progress.start(`Interpreting ${niche} lead discovery for ${geo}.`, {
        geo,
        limit,
        mock,
        niche,
      });

      try {
        // Call backend directly (bypassing frontend API route for reliability)
        const backendUrl = ZRAI_BACKEND_URL || "http://localhost:8001";
        const url = `${backendUrl}/api/v1/discover`;

        console.log(`[discoverLeads] Calling backend: ${url}`);
        progress.advance(
          1,
          mock
            ? "Using mock discovery mode for a fast dry run."
            : "Calling the live discovery backend and waiting for lead results."
        );

        const callDiscovery = async (requestedNiche: string) =>
          fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ niche: requestedNiche, geo, limit, mock }),
          });

        let response = await callDiscovery(normalizedNiche || niche);

        console.log(`[discoverLeads] Response status: ${response.status}`);

        if (!response.ok) {
          const errorText = await response.text();
          console.error("[discoverLeads] Backend error:", errorText);
          let detail: string | undefined;

          try {
            const parsed = JSON.parse(errorText) as { detail?: string };
            detail = parsed.detail;
          } catch {
            detail = errorText;
          }

          if (isBudgetConstraint(detail) && normalizedNiche !== niche) {
            console.warn(
              `[discoverLeads] Retrying discovery with normalized clinic niche after budget-style failure: ${normalizedNiche}`
            );
            response = await callDiscovery(normalizedNiche);
            if (response.ok) {
              const retryData = await response.json();
              progress.advance(
                2,
                `Normalized the clinic query and prepared ${retryData.count} discovered lead${retryData.count === 1 ? "" : "s"} for review.`,
                { discovered: retryData.count, retried: true }
              );
              progress.success(
                `Discovery complete. Prepared ${retryData.count} lead${retryData.count === 1 ? "" : "s"} for review.`,
                { discovered: retryData.count, runId: retryData.run_id ?? null }
              );
              return {
                success: true,
                leads: retryData.leads,
                count: retryData.count,
                run_id: retryData.run_id,
                summary:
                  retryData.count > 0
                    ? `Discovered ${retryData.count} real leads in the ${normalizedNiche} niche (${geo}) using the live discovery backend.`
                    : `Discovery completed for ${normalizedNiche} in ${geo}, but no verified leads matched the current filters yet.`,
                artifactTrigger: {
                  kind: "lead-list" as const,
                  data: {
                    leads: retryData.leads,
                    niche: normalizedNiche,
                    geo,
                  },
                },
              };
            }
          }

          const normalizedDetail = detail?.trim();
          const suggestion = normalizedDetail?.includes("getaddrinfo failed")
            ? "Supabase is unreachable in this local environment. Restart the backend so it can use the local memory fallback. Do not retry automatically."
            : normalizedDetail?.toLowerCase().includes("timed out")
              ? "Live discovery timed out. Stop here and ask the user whether to retry with a narrower query or smaller lead count."
              : isBudgetConstraint(normalizedDetail)
                ? "Discovery hit an upstream scraper budget constraint. Refine the niche or retry with a clinic-specific query instead of switching to mock data."
                : response.status >= 500
                  ? "The backend is up, but discovery failed inside the service. Check the backend logs for the real dependency error."
                : "Check if the ZRAI backend server is running on port 8001.";
          progress.error(
            1,
            normalizedDetail ||
              `Discovery failed with status ${response.status}.`,
            { status: response.status }
          );

          return {
            success: false,
            error: normalizedDetail || `Backend error: ${response.status}`,
            suggestion,
          };
        }

        const data = await response.json();
        console.log(`[discoverLeads] Success: ${data.count} leads discovered`);
        progress.advance(
          2,
          `Normalizing ${data.count} discovered lead${data.count === 1 ? "" : "s"} for the artifact.`,
          { discovered: data.count }
        );
        progress.success(
          `Discovery complete. Prepared ${data.count} lead${data.count === 1 ? "" : "s"} for review.`,
          { discovered: data.count, runId: data.run_id ?? null }
        );

        return {
          success: true,
          leads: data.leads,
          count: data.count,
          run_id: data.run_id,
          summary: mock
            ? `Discovered ${data.count} mock leads in the ${niche} niche (${geo}). Using test data for fast development.`
            : `Discovered ${data.count} real leads in the ${niche} niche (${geo}) using the live discovery backend.`,
          artifactTrigger: {
            kind: "lead-list" as const,
            data: {
              leads: data.leads,
              niche,
              geo,
            },
          },
        };
      } catch (error) {
        console.error("[discoverLeads] Exception:", error);
        progress.error(
          1,
          error instanceof Error ? error.message : "Network error",
          { geo, limit, mock, niche }
        );
        return {
          success: false,
          error: error instanceof Error ? error.message : "Network error",
          suggestion:
            error instanceof Error &&
            error.message.toLowerCase().includes("fetch failed")
              ? "The backend connection dropped during live discovery. Stop here and ask the user whether to retry with a narrower query or smaller lead count."
              : "Please check if the backend is running (python -m uvicorn src.api.server:app --port 8001). If you only want a fast dry run, explicitly ask for mock data.",
        };
      }
    },
  });
