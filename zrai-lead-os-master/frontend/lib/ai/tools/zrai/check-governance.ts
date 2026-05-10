/**
 * ZRAI Lead OS - Check Governance Tool
 * 
 * Checks current governance status including rate limits, budgets, and circuit breakers.
 */

import { tool } from 'ai';
import { z } from 'zod';
import { ZRAI_ENDPOINTS } from '@/lib/zrai/constants';

export const checkGovernance = tool({
  description: `Check the current governance status of the ZRAI system.
Use this tool to see rate limits, budget consumption, circuit breaker states, and agent health.
Helpful for understanding system capacity and any active restrictions.`,
  inputSchema: z.object({}),
  execute: async (_input: Record<string, never>) => {
    try {
      const response = await fetch(ZRAI_ENDPOINTS.governance, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      });

      const data = await response.json();

      if (!response.ok || !data.success) {
        return {
          success: false,
          error: data.error?.message || 'Failed to fetch governance status',
          suggestion: 'Try again later.',
        };
      }

      const { rate_limits, budgets, circuit_breakers, agent_health, kill_switches } = data.data;

      // Calculate summary stats
      const openCircuits = Object.entries(circuit_breakers).filter(([_, state]) => state === 'open');
      const degradedAgents = agent_health.filter((a: any) => a.status !== 'healthy');
      const budgetWarnings = [];

      if (budgets.llm_tokens.used / budgets.llm_tokens.limit > 0.8) {
        budgetWarnings.push('LLM tokens');
      }
      if (budgets.apify_runs.used / budgets.apify_runs.limit > 0.8) {
        budgetWarnings.push('Apify runs');
      }
      if (budgets.browser_sessions.used / budgets.browser_sessions.limit > 0.8) {
        budgetWarnings.push('Browser sessions');
      }

      return {
        success: true,
        rate_limits,
        budgets,
        circuit_breakers,
        agent_health,
        kill_switches,
        summary: `System status: ${
          openCircuits.length > 0
            ? `⚠️ ${openCircuits.length} circuit(s) open`
            : '✅ All circuits closed'
        }. ${
          degradedAgents.length > 0
            ? `${degradedAgents.length} agent(s) degraded.`
            : 'All agents healthy.'
        } ${
          budgetWarnings.length > 0
            ? `Budget warnings: ${budgetWarnings.join(', ')}.`
            : 'Budgets OK.'
        }`,
        artifactTrigger: {
          kind: 'metrics-dashboard' as const,
          data: { rate_limits, budgets, circuit_breakers, agent_health },
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
