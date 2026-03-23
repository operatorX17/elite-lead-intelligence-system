/**
 * ZRAI Lead OS - Enrich Lead Tool
 *
 * Enriches a lead with additional contact and company data.
 */

import { tool, type UIMessageStreamWriter } from "ai";
import { z } from "zod";
import type { ChatMessage } from "@/lib/types";
import { ZRAI_BACKEND_ENDPOINTS } from "@/lib/zrai/constants";
import { createZRAIProgressReporter } from "./progress";

export const enrichLead = ({
  dataStream,
}: {
  dataStream: UIMessageStreamWriter<ChatMessage>;
}) =>
  tool({
    description: `Enrich a lead with additional data including contact information, company details, and social profiles.
Use this tool when you need more information about a specific lead, such as email addresses, phone numbers, or LinkedIn profiles.`,
    inputSchema: z.object({
      lead_id: z
        .string()
        .uuid()
        .describe("The unique identifier of the lead to enrich"),
    }),
    execute: async ({ lead_id }) => {
      const progress = createZRAIProgressReporter({
        dataStream,
        tool: "enrichLead",
        title: "Enriching lead record",
        stages: ["Load lead", "Fetch enrichment", "Prepare lead card"],
      });
      progress.start("Loading the lead and preparing the enrichment request.", {
        leadId: lead_id,
      });
      try {
        progress.advance(
          1,
          "Calling the enrichment agent for contact and company signals."
        );
        const response = await fetch(ZRAI_BACKEND_ENDPOINTS.enrich, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ lead_id }),
        });

        const data = await response.json();

        if (!response.ok || !data.success) {
          progress.error(1, data.error?.message || "Failed to enrich lead", {
            status: response.status,
          });
          return {
            success: false,
            error: data.error?.message || "Failed to enrich lead",
            suggestion:
              data.error?.code === "not_found"
                ? "Lead not found. Please check the lead ID."
                : "Try again or check if the lead exists.",
          };
        }

        const { lead, enrichment } = data;
        const contactCount = lead.contacts?.length || 0;
        progress.advance(
          2,
          `Preparing ${lead.company_name} with ${contactCount} enriched contact${contactCount === 1 ? "" : "s"}.`,
          { contacts: contactCount }
        );
        progress.success(`Lead enrichment complete for ${lead.company_name}.`, {
          contacts: contactCount,
          hasEmail: Boolean(enrichment.email),
          hasLinkedin: Boolean(enrichment.linkedin_url),
          hasPhone: Boolean(enrichment.phone),
        });

        return {
          success: true,
          lead,
          enrichment,
          summary: `Enriched ${lead.company_name} with ${contactCount} contact(s). Found: ${
            enrichment.email ? "email" : ""
          }${enrichment.phone ? ", phone" : ""}${enrichment.linkedin_url ? ", LinkedIn" : ""}.`,
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
