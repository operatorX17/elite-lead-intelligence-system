/**
 * ZRAI Lead OS - Send Outreach Tool (APPROVAL REQUIRED)
 *
 * Sends an outreach message to a lead. Requires user approval before execution.
 */

import { tool } from "ai";
import { z } from "zod";
import { ZRAI_BACKEND_ENDPOINTS } from "@/lib/zrai/constants";

export const sendOutreach = tool({
  description: `Send an outreach message to a lead.
⚠️ REQUIRES APPROVAL: This action will send a real message to the lead.
Use this tool only after drafting and reviewing the message.
The user must approve this action before it executes.`,
  inputSchema: z.object({
    lead_id: z.string().uuid().describe("The unique identifier of the lead"),
    channel: z
      .enum(["email", "linkedin", "sms", "whatsapp"])
      .describe("The communication channel"),
    message_id: z
      .string()
      .uuid()
      .describe("The ID of the drafted message to send"),
    message: z
      .string()
      .optional()
      .describe(
        "Optional: Override the message content (if not provided, uses the drafted message)"
      ),
  }),
  // CRITICAL: This tool requires user approval before execution
  needsApproval: true,
  execute: async ({ lead_id, channel, message_id, message }) => {
    try {
      const response = await fetch(ZRAI_BACKEND_ENDPOINTS.outreach, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          lead_id,
          channel,
          message_id,
          message,
          action: "send",
        }),
      });

      const data = await response.json();

      if (!response.ok || !data.success) {
        return {
          success: false,
          error: data.error?.message || "Failed to send outreach",
          suggestion:
            data.error?.code === "not_found"
              ? "Lead or message not found. Please check the IDs."
              : data.error?.code === "do_not_contact"
                ? "This lead is on the do-not-contact list. Cannot send."
                : data.error?.code === "rate_limit"
                  ? "Rate limit exceeded. Try again later."
                  : data.error?.code === "governance_violation"
                    ? "This message violates governance rules."
                    : "Check the message and try again.",
        };
      }

      const { message: sentMessage, sent } = data.data;

      return {
        success: true,
        message: sentMessage,
        sent,
        summary: sent
          ? `✅ Successfully sent ${channel} message to the lead. Message ID: ${sentMessage.id}`
          : `Message queued for delivery. Status: ${sentMessage.status}`,
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : "Network error",
        suggestion: "Please check your connection and try again.",
      };
    }
  },
});
