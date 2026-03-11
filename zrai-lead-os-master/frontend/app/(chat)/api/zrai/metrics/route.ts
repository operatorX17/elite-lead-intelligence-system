/**
 * ZRAI Lead OS - Metrics Endpoint
 * 
 * GET /api/zrai/metrics
 * Returns system metrics including reply rates, meeting rates, and budget consumption.
 */

import { z } from 'zod';
import { auth } from '@/app/(auth)/auth';
import { ZRAI_BACKEND_URL } from '@/lib/zrai/constants';
import { authError, backendError, validationError } from '@/lib/zrai/errors';
import type { SystemMetrics } from '@/lib/zrai/types';

// ============================================================================
// Query Schema
// ============================================================================

const metricsQuerySchema = z.object({
  period: z.enum(['daily', 'weekly', 'monthly']).optional().default('daily'),
});

type MetricsQuery = z.infer<typeof metricsQuerySchema>;

// ============================================================================
// Response Types
// ============================================================================

interface MetricsResponse {
  success: boolean;
  data?: SystemMetrics;
  error?: {
    code: string;
    message: string;
  };
}

// ============================================================================
// Route Handler
// ============================================================================

export async function GET(request: Request): Promise<Response> {
  try {
    // Authenticate
    const session = await auth();
    if (!session?.user) {
      return authError('metrics').toResponse();
    }

    // Parse query parameters
    const url = new URL(request.url);
    let query: MetricsQuery;
    try {
      const params = Object.fromEntries(url.searchParams.entries());
      query = metricsQuerySchema.parse(params);
    } catch (error) {
      if (error instanceof z.ZodError) {
        return validationError('metrics', {
          errors: error.errors.map((e) => ({
            field: e.path.join('.'),
            message: e.message,
          })),
        }).toResponse();
      }
      return validationError('metrics', { message: 'Invalid query parameters' }).toResponse();
    }

    // Call ZRAI backend
    const backendResponse = await fetch(
      `${ZRAI_BACKEND_URL}/api/v1/metrics?period=${query.period}`,
      {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'X-User-ID': session.user.id,
        },
      }
    );

    if (!backendResponse.ok) {
      const errorData = await backendResponse.json().catch(() => ({}));
      return backendError('metrics', errorData.message).toResponse();
    }

    const data = await backendResponse.json();

    const response: MetricsResponse = {
      success: true,
      data: {
        period: query.period,
        reply_rate: data.reply_rate || 0,
        meeting_rate: data.meeting_rate || 0,
        cost_per_meeting: data.cost_per_meeting || 0,
        leads_discovered: data.leads_discovered || 0,
        leads_qualified: data.leads_qualified || 0,
        outreach_sent: data.outreach_sent || 0,
        budget: data.budget || {
          llm_tokens: { used: 0, limit: 0 },
          apify_runs: { used: 0, limit: 0 },
          browser_sessions: { used: 0, limit: 0 },
        },
        agent_health: data.agent_health || {},
        trends: data.trends || [],
      },
    };

    return Response.json(response, { status: 200 });
  } catch (error) {
    console.error('[ZRAI:metrics] Error:', error);
    return backendError('metrics', error instanceof Error ? error.message : 'Unknown error').toResponse();
  }
}
