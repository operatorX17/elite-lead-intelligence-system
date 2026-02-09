/**
 * ZRAI Lead OS - Draft Outreach Tool
 * 
 * Drafts personalized outreach messages for leads.
 */

import { tool } from 'ai';
import { z } from 'zod';
import { ZRAI_ENDPOINTS } from '@/lib/zrai/constants';

export const draftOutreach = tool({
  description: `Draft a personalized outreach message for a lead.
Use this tool to create email, LinkedIn, or SMS messages based on the lead's profile and intent signals.
The message follows the 4-part structure: Observation, Impact, Offer, and CTA.
This tool only drafts the message - it does NOT send it.`,
  inputSchema: z.object({
    lead_id: z
      .string()
      .uuid()
      .describe('The unique identifier of the lead'),
    channel: z
      .enum(['email', 'linkedin', 'sms'])
      .describe('The communication channel: email, linkedin, or sms'),
  }),
  execute: async ({ lead_id, channel }) => {
    try {
      const response = await fetch(ZRAI_ENDPOINTS.outreach, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lead_id, channel, action: 'draft' }),
      });

      const data = await response.json();

      if (!response.ok || !data.success) {
        return {
          success: false,
          error: data.error?.message || 'Failed to draft outreach',
          suggestion: data.error?.code === 'not_found'
            ? 'Lead not found. Please check the lead ID.'
            : data.error?.code === 'do_not_contact'
            ? 'This lead is on the do-not-contact list.'
            : 'Try enriching the lead first to get contact information.',
        };
      }

      const { message } = data.data;

      return {
        success: true,
        message,
        summary: `Drafted ${channel} message for the lead. Subject: "${message.subject || 'N/A'}". Message ID: ${message.id}. Review and approve before sending.`,
        artifactTrigger: {
          kind: 'outreach-draft' as const,
          data: { message, channel },
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
