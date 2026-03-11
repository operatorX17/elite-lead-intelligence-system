/**
 * ZRAI Lead OS - Discover Leads Tool
 * 
 * Discovers leads based on niche and geo via the ZRAI Discovery Agent.
 */

import { tool } from 'ai';
import { z } from 'zod';
import {
  DEFAULT_DISCOVERY_LIMIT,
  MAX_DISCOVERY_LIMIT,
  ZRAI_ENDPOINTS,
} from '@/lib/zrai/constants';

export const discoverLeads = tool({
  description: `Discover new leads based on niche and geographic location. 
Use this tool when the user wants to find new prospects or leads in a specific industry or region.
Returns a list of discovered leads with basic company information.`,
  inputSchema: z.object({
    niche: z
      .string()
      .describe('The industry niche to search for (e.g., "saas", "ecommerce", "agency", "fintech")'),
    geo: z
      .string()
      .optional()
      .default('us')
      .describe('Geographic region to search (e.g., "us", "uk", "eu", "global")'),
    limit: z
      .number()
      .min(1)
      .max(MAX_DISCOVERY_LIMIT)
      .optional()
      .default(DEFAULT_DISCOVERY_LIMIT)
      .describe('Maximum number of leads to discover (1-200)'),
  }),
  execute: async ({ niche, geo, limit }) => {
    try {
      const response = await fetch(ZRAI_ENDPOINTS.discover, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ niche, geo, limit }),
      });

      const data = await response.json();

      if (!response.ok || !data.success) {
        return {
          success: false,
          error: data.error?.message || 'Failed to discover leads',
          suggestion: data.error?.code === 'rate_limit' 
            ? 'Rate limit exceeded. Please try again later.'
            : data.error?.code === 'budget_exceeded'
            ? 'Daily budget exceeded. Try again tomorrow.'
            : 'Check your parameters and try again.',
        };
      }

      return {
        success: true,
        leads: data.data.leads,
        count: data.data.count,
        run_id: data.data.run_id,
        summary: `Discovered ${data.data.count} leads in the ${niche} niche (${geo}).`,
        artifactTrigger: {
          kind: 'lead-list' as const,
          data: {
            leads: data.data.leads,
            niche,
            geo,
          },
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
