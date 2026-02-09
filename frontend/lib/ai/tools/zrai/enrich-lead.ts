/**
 * ZRAI Lead OS - Enrich Lead Tool
 * 
 * Enriches a lead with additional contact and company data.
 */

import { tool } from 'ai';
import { z } from 'zod';
import { ZRAI_ENDPOINTS } from '@/lib/zrai/constants';

export const enrichLead = tool({
  description: `Enrich a lead with additional data including contact information, company details, and social profiles.
Use this tool when you need more information about a specific lead, such as email addresses, phone numbers, or LinkedIn profiles.`,
  inputSchema: z.object({
    lead_id: z
      .string()
      .uuid()
      .describe('The unique identifier of the lead to enrich'),
  }),
  execute: async ({ lead_id }) => {
    try {
      const response = await fetch(ZRAI_ENDPOINTS.enrich, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lead_id }),
      });

      const data = await response.json();

      if (!response.ok || !data.success) {
        return {
          success: false,
          error: data.error?.message || 'Failed to enrich lead',
          suggestion: data.error?.code === 'not_found'
            ? 'Lead not found. Please check the lead ID.'
            : 'Try again or check if the lead exists.',
        };
      }

      const { lead, enrichment } = data.data;
      const contactCount = lead.contacts?.length || 0;

      return {
        success: true,
        lead,
        enrichment,
        summary: `Enriched ${lead.company_name} with ${contactCount} contact(s). Found: ${
          enrichment.email ? 'email' : ''
        }${enrichment.phone ? ', phone' : ''}${enrichment.linkedin_url ? ', LinkedIn' : ''}.`,
        artifactTrigger: {
          kind: 'lead-card' as const,
          data: { lead, enrichment },
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
