/**
 * ZRAI Lead OS - Handle Conversation Tool
 *
 * Handles lead conversations and generates AI responses.
 */

import { tool, type UIMessageStreamWriter } from "ai";
import { z } from "zod";
import type { ChatMessage } from "@/lib/types";
import { ZRAI_BACKEND_ENDPOINTS } from "@/lib/zrai/constants";
import { toConversation } from "@/lib/zrai/transformers";
import { createZRAIProgressReporter } from "./progress";

export const handleConversation = ({
  dataStream,
}: {
  dataStream: UIMessageStreamWriter<ChatMessage>;
}) =>
  tool({
    description: `Handle a conversation with a lead by processing their message and generating an AI response.
Use this tool when a lead replies to outreach and you need to continue the conversation.
The AI will analyze the message for qualification signals and generate an appropriate response.`,
    inputSchema: z.object({
      lead_id: z.string().uuid().describe("The unique identifier of the lead"),
      message: z
        .string()
        .min(1)
        .describe("The message from the lead to process"),
      channel: z
        .enum(["email", "linkedin", "sms", "whatsapp"])
        .optional()
        .describe(
          "The communication channel (optional, will be inferred if not provided)"
        ),
    }),
    execute: async ({ lead_id, message, channel }) => {
      const progress = createZRAIProgressReporter({
        dataStream,
        tool: "handleConversation",
        title: "Processing lead conversation",
        stages: ["Load conversation", "Generate reply", "Prepare thread view"],
      });
      progress.start(
        "Loading the conversation context for the incoming reply.",
        {
          channel: channel ?? null,
          leadId: lead_id,
        }
      );
      try {
        progress.advance(
          1,
          "Analyzing the incoming message and generating the next response."
        );
        const response = await fetch(ZRAI_BACKEND_ENDPOINTS.conversation, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ lead_id, message, channel }),
        });

        const data = await response.json();

        if (!response.ok || !data.success) {
          progress.error(
            1,
            data.error?.message || "Failed to handle conversation",
            { status: response.status }
          );
          return {
            success: false,
            error: data.error?.message || "Failed to handle conversation",
            suggestion:
              data.error?.code === "not_found"
                ? "Lead not found. Please check the lead ID."
                : "Try again or check if the lead has an active conversation.",
          };
        }

        const conversation = toConversation(data.conversation, channel);
        const ai_response = data.response;
        const needs_escalation = Boolean(data.needs_escalation);
        const escalation_reason = data.escalation_reason;
        progress.advance(
          2,
          "Preparing the updated conversation thread for review.",
          {
            escalated: needs_escalation,
            messageCount: conversation.messages.length,
          }
        );
        progress.success(
          needs_escalation
            ? "Conversation processed and flagged for human escalation."
            : "Conversation processed and the AI response is ready."
        );

        return {
          success: true,
          conversation,
          ai_response,
          needs_escalation,
          escalation_reason,
          summary: needs_escalation
            ? `Escalation recommended: ${escalation_reason}. AI response generated but human review is needed.`
            : `Processed the lead reply. Conversation status: ${conversation.status}. AI response ready.`,
          artifactTrigger: {
            kind: "conversation-thread" as const,
            data: {
              messages: conversation.messages,
              leadId: conversation.lead_id,
              status: conversation.status,
            },
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
