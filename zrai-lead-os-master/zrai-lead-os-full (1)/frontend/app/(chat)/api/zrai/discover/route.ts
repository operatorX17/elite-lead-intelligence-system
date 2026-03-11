/**
 * ZRAI Lead OS - Discovery Endpoint
 * 
 * POST /api/zrai/discover
 * Triggers lead discovery via the ZRAI Discovery Agent.
 */

import { z } from 'zod';
import { auth } from '@/app/(auth)/auth';
import {
  DEFAULT_DISCOVERY_LIMIT,
  MAX_DISCOVERY_LIMIT,
  ZRAI_BACKEND_URL,
} from '@/lib/zrai/constants';
import {
  authError,
  backendError,
  validationError,
  ZRAIAPIError,
} from '@/lib/zrai/errors';
import type { Lead } from '@/lib/zrai/types';

// ============================================================================
// Request Schema
// ============================================================================

const discoverRequestSchema = z.object({
  niche: z.string().min(1, 'Niche is required'),
  geo: z.string().optional().default('us'),
  limit: z.number().min(1).max(MAX_DISCOVERY_LIMIT).optional().default(DEFAULT_DISCOVERY_LIMIT),
});

type DiscoverRequest = z.infer<typeof discoverRequestSchema>;

// ============================================================================
// Response Types
// ============================================================================

interface DiscoverResponse {
  success: boolean;
  data?: {
    leads: Lead[];
    count: number;
    run_id: string;
  };
  error?: {
    code: string;
    message: string;
  };
}

// ============================================================================
// Route Handler
// ============================================================================

export async function POST(request: Request): Promise<Response> {
  try {
    // Authenticate
    const session = await auth();
    if (!session?.user) {
      return authError('discover').toResponse();
    }

    // Parse and validate request
    let body: DiscoverRequest;
    try {
      const json = await request.json();
      body = discoverRequestSchema.parse(json);
    } catch (error) {
      if (error instanceof z.ZodError) {
        return validationError('discover', {
          errors: error.errors.map((e) => ({
            field: e.path.join('.'),
            message: e.message,
          })),
        }).toResponse();
      }
      return validationError('discover', { message: 'Invalid JSON body' }).toResponse();
    }

    // Call ZRAI backend
    const backendResponse = await fetch(`${ZRAI_BACKEND_URL}/api/v1/discover`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-User-ID': session.user.id,
      },
      body: JSON.stringify({
        niche: body.niche,
        geo: body.geo,
        limit: body.limit,
      }),
    });

    if (!backendResponse.ok) {
      const errorData = await backendResponse.json().catch(() => ({}));
      
      // Map backend errors to ZRAI errors
      if (backendResponse.status === 429) {
        return new ZRAIAPIError(
          'rate_limit',
          'discover',
          errorData.message || 'Rate limit exceeded',
          undefined,
          errorData.retry_after
        ).toResponse();
      }

      if (backendResponse.status === 402) {
        return new ZRAIAPIError(
          'budget_exceeded',
          'discover',
          errorData.message || 'Budget exceeded for discovery'
        ).toResponse();
      }

      if (backendResponse.status === 503) {
        return new ZRAIAPIError(
          'circuit_open',
          'discover',
          errorData.message || 'Discovery agent is temporarily unavailable'
        ).toResponse();
      }

      return backendError('discover', errorData.message).toResponse();
    }

    const data = await backendResponse.json();

    const response: DiscoverResponse = {
      success: true,
      data: {
        leads: data.leads || [],
        count: data.count || data.leads?.length || 0,
        run_id: data.run_id || '',
      },
    };

    return Response.json(response, { status: 200 });
  } catch (error) {
    console.error('[ZRAI:discover] Error:', error);
    return backendError('discover', error instanceof Error ? error.message : 'Unknown error').toResponse();
  }
}
