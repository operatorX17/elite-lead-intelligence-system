/**
 * ZRAI Lead OS - Manage A/B Test Tool
 * 
 * Creates and manages A/B tests for outreach optimization.
 */

import { tool } from 'ai';
import { z } from 'zod';
import { ZRAI_ENDPOINTS } from '@/lib/zrai/constants';

export const manageABTest = tool({
  description: `Create and manage A/B tests for outreach optimization.
Use this tool to test different outreach variants and measure their performance.
Supports creating new tests, starting/pausing tests, and viewing results.`,
  inputSchema: z.object({
    action: z
      .enum(['create', 'start', 'pause', 'conclude', 'view'])
      .describe('The action to perform: create a new test, start/pause/conclude an existing test, or view results'),
    test_id: z
      .string()
      .uuid()
      .optional()
      .describe('The test ID (required for start, pause, conclude, view actions)'),
    name: z
      .string()
      .optional()
      .describe('Test name (required for create action)'),
    description: z
      .string()
      .optional()
      .describe('Test description (optional for create action)'),
    variants: z
      .array(z.object({
        name: z.string(),
        description: z.string().optional(),
        config: z.record(z.unknown()),
      }))
      .optional()
      .describe('Test variants (required for create action, minimum 2)'),
    metric: z
      .string()
      .optional()
      .describe('Primary metric to measure (required for create action, e.g., "reply_rate", "meeting_rate")'),
  }),
  execute: async ({ action, test_id, name, description, variants, metric }) => {
    try {
      // Validate required params based on action
      if (action === 'create') {
        if (!name || !variants || variants.length < 2 || !metric) {
          return {
            success: false,
            error: 'Create action requires name, at least 2 variants, and metric',
            suggestion: 'Provide all required parameters for creating a test.',
          };
        }
      } else if (action !== 'view' && !test_id) {
        return {
          success: false,
          error: `${action} action requires test_id`,
          suggestion: 'Provide the test ID to perform this action.',
        };
      }

      // Handle view action
      if (action === 'view') {
        const url = test_id ? `${ZRAI_ENDPOINTS.abTest}/${test_id}` : ZRAI_ENDPOINTS.abTest;
        const response = await fetch(url, {
          method: 'GET',
          headers: { 'Content-Type': 'application/json' },
        });

        const data = await response.json();

        if (!response.ok || !data.success) {
          return {
            success: false,
            error: data.error?.message || 'Failed to fetch A/B test',
            suggestion: 'Check the test ID and try again.',
          };
        }

        return {
          success: true,
          test: data.data,
          summary: test_id
            ? `A/B Test "${data.data.name}": Status ${data.data.status}. ${
                data.data.winner ? `Winner: ${data.data.winner}` : 'No winner yet.'
              }`
            : `Found ${Array.isArray(data.data) ? data.data.length : 0} A/B test(s).`,
          artifactTrigger: {
            kind: 'metrics-dashboard' as const,
            data: { abTest: data.data },
          },
        };
      }

      // Handle create/start/pause/conclude actions
      const body = action === 'create'
        ? { action, name, description, variants, metric }
        : { action, test_id };

      const response = await fetch(ZRAI_ENDPOINTS.abTest, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      const data = await response.json();

      if (!response.ok || !data.success) {
        return {
          success: false,
          error: data.error?.message || `Failed to ${action} A/B test`,
          suggestion: 'Check your parameters and try again.',
        };
      }

      const test = data.data;
      const actionMessages: Record<string, string> = {
        create: `Created A/B test "${test.name}" with ${test.variants?.length || 0} variants.`,
        start: `Started A/B test "${test.name}".`,
        pause: `Paused A/B test "${test.name}".`,
        conclude: `Concluded A/B test "${test.name}". ${test.winner ? `Winner: ${test.winner}` : 'No clear winner.'}`,
      };

      return {
        success: true,
        test,
        summary: actionMessages[action] || `A/B test action "${action}" completed.`,
        artifactTrigger: {
          kind: 'metrics-dashboard' as const,
          data: { abTest: test },
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
