/**
 * ZRAI Lead OS - Approve Escalation Tool (APPROVAL REQUIRED)
 * 
 * Escalates a lead conversation to human handling. Requires user approval.
 */

import { tool } from 'ai';
import { z } from 'zod';
import { ZRAI_ENDPOINTS } from '@/lib/zrai/constants';

export const approveEscalation = tool({
  description: `Escalate a lead conversation to human handling.
⚠️ REQUIRES APPROVAL: This action will mark the lead for human follow-up.
Use this tool when the AI conversation agent recommends escalation or when the lead requires human attention.`,
  inputSchema: z.object({
    lead_id: z
      .string()
      .uuid()
      .describe('The unique identifier of the lead'),
    reason: z
      .string()
      .min(1)
      .describe('The reason for escalation (e.g., "High-value opportunity", "Complex technical questions", "Pricing negotiation")'),
    assignee: z
      .string()
      .optional()
      .describe('Optional: Specific person to assign the escalation to'),
  }),
  // CRITICAL: This tool requires user approval before execution
  needsApproval: true,
  execute: async ({ lead_id, reason, assignee }) => {
    try {
      const response = await fetch(`${ZRAI_ENDPOINTS.conversation}/escalate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lead_id, reason, assignee }),
      });

      const data = await response.json();

      if (!response.ok || !data.success) {
        return {
          success: false,
          error: data.error?.message || 'Failed to escalate',
          suggestion: data.error?.code === 'not_found'
            ? 'Lead or conversation not found. Please check the lead ID.'
            : 'Try again or check if the lead has an active conversation.',
        };
      }

      const { conversation, escalated } = data.data;

      return {
        success: true,
        conversation,
        escalated,
        summary: escalated
          ? `✅ Lead escalated to human handling. Reason: ${reason}. ${
              assignee ? `Assigned to: ${assignee}` : 'Awaiting assignment.'
            }`
          : 'Escalation request processed.',
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
