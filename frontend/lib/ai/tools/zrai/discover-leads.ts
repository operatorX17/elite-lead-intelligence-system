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
  ZRAI_BACKEND_URL,
} from '@/lib/zrai/constants';

export const discoverLeads = tool({
  description: `Discover new leads based on niche and geographic location. 
Use this tool when the user wants to find new prospects or leads in a specific industry or region.
Returns a list of discovered leads with basic company information.

NOTE: Discovery can take 2-5 minutes as it scrapes real data from Google Maps. 
Set mock=true for instant test data during development.`,
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
      .default(20)
      .describe('Maximum number of leads to discover (1-200)'),
    mock: z
      .boolean()
      .optional()
      .default(true) // Default to mock in development for faster testing
      .describe('Use mock data for instant results (recommended for testing)'),
  }),
  execute: async ({ niche, geo, limit, mock }) => {
    console.log(`[discoverLeads] Starting discovery: niche=${niche}, geo=${geo}, limit=${limit}, mock=${mock}`);
    
    try {
      // Call backend directly (bypassing frontend API route for reliability)
      const backendUrl = ZRAI_BACKEND_URL || 'http://localhost:8000';
      const url = `${backendUrl}/api/v1/discover`;
      
      console.log(`[discoverLeads] Calling backend: ${url}`);
      
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ niche, geo, limit, mock }),
      });

      console.log(`[discoverLeads] Response status: ${response.status}`);

      if (!response.ok) {
        const errorText = await response.text();
        console.error('[discoverLeads] Backend error:', errorText);
        return {
          success: false,
          error: `Backend error: ${response.status}`,
          suggestion: 'Check if the backend server is running on port 8000.',
        };
      }

      const data = await response.json();
      console.log(`[discoverLeads] Success: ${data.count} leads discovered`);

      return {
        success: true,
        leads: data.leads,
        count: data.count,
        run_id: data.run_id,
        summary: mock 
          ? `Discovered ${data.count} mock leads in the ${niche} niche (${geo}). Using test data for fast development.`
          : `Discovered ${data.count} real leads in the ${niche} niche (${geo}) from Google Maps.`,
        artifactTrigger: {
          kind: 'lead-list' as const,
          data: {
            leads: data.leads,
            niche,
            geo,
          },
        },
      };
    } catch (error) {
      console.error('[discoverLeads] Exception:', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        suggestion: 'Please check if the backend is running (python -m uvicorn src.api.server:app --port 8000). If the issue persists, try using mock=true for testing.',
      };
    }
  },
});
