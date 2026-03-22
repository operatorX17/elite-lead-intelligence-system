/**
 * ZRAI Lead OS - Draft Outreach Tool
 *
 * Drafts personalized outreach messages for leads.
 */

import { tool, type UIMessageStreamWriter } from "ai";
import { z } from "zod";
import type { ChatMessage } from "@/lib/types";
import { ZRAI_BACKEND_ENDPOINTS } from "@/lib/zrai/constants";
import { toOutreachMessage } from "@/lib/zrai/transformers";
import { createZRAIProgressReporter } from "./progress";

export const draftOutreach = ({
  dataStream,
}: {
  dataStream: UIMessageStreamWriter<ChatMessage>;
}) =>
  tool({
    description: `Draft a personalized outreach message for a lead.
Use this tool to create email, LinkedIn, or SMS messages based on the lead's profile and intent signals.
The message follows the 4-part structure: Observation, Impact, Offer, and CTA.
This tool only drafts the message - it does NOT send it.`,
    inputSchema: z.object({
      lead_id: z.string().uuid().describe("The unique identifier of the lead"),
      channel: z
        .enum(["email", "linkedin", "sms"])
        .describe("The communication channel: email, linkedin, or sms"),
    }),
    execute: async ({ lead_id, channel }) => {
      const progress = createZRAIProgressReporter({
        dataStream,
        tool: "draftOutreach",
        title: "Drafting outreach message",
        stages: ["Load lead context", "Generate message", "Prepare draft"],
      });
      progress.start(
        "Loading lead context and the requested outreach channel.",
        {
          channel,
          leadId: lead_id,
        }
      );
      try {
        progress.advance(
          1,
          `Generating a ${channel} draft with evidence-backed messaging.`
        );
        const response = await fetch(ZRAI_BACKEND_ENDPOINTS.outreach, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ lead_id, channel, action: "draft" }),
        });

        const data = await response.json();

        if (!response.ok || !data.success) {
          progress.error(1, data.error?.message || "Failed to draft outreach", {
            status: response.status,
          });
          return {
            success: false,
            error: data.error?.message || "Failed to draft outreach",
            suggestion:
              data.error?.code === "not_found"
                ? "Lead not found. Please check the lead ID."
                : data.error?.code === "do_not_contact"
                  ? "This lead is on the do-not-contact list."
                  : "Try enriching the lead first to get contact information.",
          };
        }

        const message = toOutreachMessage(data.outreach?.[0] ?? {}, channel);
        progress.advance(2, `Preparing the ${channel} draft for review.`, {
          hasSubject: Boolean(message.subject),
          messageId: message.id,
        });
        progress.success("Outreach draft is ready for review.");

        return {
          success: true,
          message,
          summary: `Drafted ${channel} message for the lead. Subject: "${message.subject || "N/A"}". Message ID: ${message.id}. Review and approve before sending.`,
          artifactTrigger: {
            kind: "outreach-draft" as const,
            data: message,
          },
        };
      } catch (error) {
        progress.error(
          1,
          error instanceof Error ? error.message : "Network error",
          { channel, leadId: lead_id }
        );
        return {
          success: false,
          error: error instanceof Error ? error.message : "Network error",
          suggestion: "Please check your connection and try again.",
        };
      }
    },
  });
