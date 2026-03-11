/**
 * ZRAI Lead OS - Handle Conversation Tool
 * 
 * Handles lead conversations and generates AI responses.
 */

import { tool } from 'ai';
import { z } from 'zod';
import { ZRAI_ENDPOINTS } from '@/lib/zrai/constants';

export const handleConversation = tool({
  description: `Handle a conversation with a lead by processing their message and generating an AI response.
Use this tool when a lead replies to outreach and you need to continue the conversation.
The AI will analyze the message for qualification signals and generate an appropriate response.`,
  inputSchema: z.object({
    lead_id: z
      .string()
      .uuid()
      .describe('The unique identifier of the lead'),
    message: z
      .string()
      .min(1)
      .describe('The message from the lead to process'),
    channel: z
      .enum(['email', 'linkedin', 'sms'])
      .optional()
      .describe('The communication channel (optional, will be inferred if not provided)'),
  }),
  execute: async ({ lead_id, message, channel }) => {
    try {
      const response = await fetch(ZRAI_ENDPOINTS.conversation, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lead_id, message, channel }),
      });

      const data = await response.json();

      if (!response.ok || !data.success) {
        return {
          success: false,
          error: data.error?.message || 'Failed to handle conversation',
          suggestion: data.error?.code === 'not_found'
            ? 'Lead not found. Please check the lead ID.'
            : 'Try again or check if the lead has an active conversation.',
        };
      }

      const { conversation, ai_response, needs_escalation, escalation_reason } = data.data;

      return {
        success: true,
        conversation,
        ai_response,
        needs_escalation,
        escalation_reason,
        summary: needs_escalation
          ? `⚠️ Escalation recommended: ${escalation_reason}. AI response generated but human review needed.`
          : `Processed lead message. Conversation status: ${conversation.status}. AI response ready.`,
        artifactTrigger: {
          kind: 'conversation-thread' as const,
          data: { conversation, ai_response, needs_escalation },
        },
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        suggestion: 'Please check your connection and try again.',
      };
    }
  },
});
