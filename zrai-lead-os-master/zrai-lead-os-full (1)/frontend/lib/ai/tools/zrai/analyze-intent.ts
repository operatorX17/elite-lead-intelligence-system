/**
 * ZRAI Lead OS - Analyze Intent Tool
 * 
 * Analyzes intent signals and revenue leak indicators for a lead.
 */

import { tool } from 'ai';
import { z } from 'zod';
import { ZRAI_ENDPOINTS } from '@/lib/zrai/constants';

export const analyzeIntent = tool({
  description: `Analyze a lead's intent signals and revenue leak indicators.
Use this tool to understand how likely a lead is to be interested in your offer based on their online behavior, tech stack, and business signals.
Returns intent signals with confidence scores and an overall revenue leak score.`,
  inputSchema: z.object({
    lead_id: z
      .string()
      .uuid()
      .describe('The unique identifier of the lead to analyze'),
  }),
  execute: async ({ lead_id }) => {
    try {
      const response = await fetch(ZRAI_ENDPOINTS.intent, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lead_id }),
      });

      const data = await response.json();

      if (!response.ok || !data.success) {
        return {
          success: false,
          error: data.error?.message || 'Failed to analyze intent',
          suggestion: data.error?.code === 'not_found'
            ? 'Lead not found. Please check the lead ID.'
            : 'Try again or enrich the lead first.',
        };
      }

      const { lead, intent_signals, revenue_leak_score } = data.data;
      const signalCount = intent_signals?.length || 0;
      const highConfidenceSignals = intent_signals?.filter((s: any) => s.confidence > 0.7) || [];

      return {
        success: true,
        lead,
        intent_signals,
        revenue_leak_score,
        summary: `Found ${signalCount} intent signal(s) for ${lead.company_name}. Revenue leak score: ${revenue_leak_score}/100. ${
          highConfidenceSignals.length > 0
            ? `High-confidence signals: ${highConfidenceSignals.map((s: any) => s.signal_type).join(', ')}.`
            : 'No high-confidence signals detected.'
        }`,
        artifactTrigger: {
          kind: 'lead-card' as const,
          data: { lead, intent_signals, revenue_leak_score },
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
