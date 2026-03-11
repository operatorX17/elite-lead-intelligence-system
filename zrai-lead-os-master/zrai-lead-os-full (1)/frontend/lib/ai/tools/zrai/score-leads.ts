/**
 * ZRAI Lead OS - Score Leads Tool
 * 
 * Scores leads based on intent, fit, engagement, and recency.
 */

import { tool } from 'ai';
import { z } from 'zod';
import { ZRAI_ENDPOINTS } from '@/lib/zrai/constants';

export const scoreLeads = tool({
  description: `Score leads based on intent, fit, engagement, and recency factors.
Use this tool to prioritize your pipeline and identify the most promising leads.
Returns ranked leads with detailed score breakdowns.`,
  inputSchema: z.object({
    niche: z
      .string()
      .optional()
      .describe('Filter by niche (e.g., "saas", "ecommerce")'),
    geo: z
      .string()
      .optional()
      .describe('Filter by geographic region'),
    min_score: z
      .number()
      .min(0)
      .max(100)
      .optional()
      .describe('Minimum score threshold (0-100)'),
    lead_ids: z
      .array(z.string().uuid())
      .optional()
      .describe('Specific lead IDs to score (if not provided, scores all eligible leads)'),
  }),
  execute: async ({ niche, geo, min_score, lead_ids }) => {
    try {
      const response = await fetch(ZRAI_ENDPOINTS.score, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ niche, geo, min_score, lead_ids }),
      });

      const data = await response.json();

      if (!response.ok || !data.success) {
        return {
          success: false,
          error: data.error?.message || 'Failed to score leads',
          suggestion: 'Try again or check if leads exist.',
        };
      }

      const { results, count } = data.data;
      const qualifiedCount = results.filter((r: any) => !r.disqualified).length;
      const topLead = results[0];

      return {
        success: true,
        results,
        count,
        summary: `Scored ${count} lead(s). ${qualifiedCount} qualified, ${count - qualifiedCount} disqualified. ${
          topLead
            ? `Top lead: ${topLead.lead.company_name} (score: ${topLead.score_breakdown.total_score})`
            : ''
        }`,
        artifactTrigger: {
          kind: 'scoring-dashboard' as const,
          data: { results, filters: { niche, geo, min_score } },
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
