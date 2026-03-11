/**
 * ZRAI Lead OS - Governance Endpoint
 * 
 * GET /api/zrai/governance
 * Returns current governance status including rate limits, budgets, and circuit breakers.
 */

import { auth } from '@/app/(auth)/auth';
import { ZRAI_BACKEND_URL } from '@/lib/zrai/constants';
import { authError, backendError } from '@/lib/zrai/errors';
import type { GovernanceStatus } from '@/lib/zrai/types';

// ============================================================================
// Response Types
// ============================================================================

interface GovernanceResponse {
  success: boolean;
  data?: GovernanceStatus;
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
      return authError('governance').toResponse();
    }

    // Call ZRAI backend
    const backendResponse = await fetch(`${ZRAI_BACKEND_URL}/api/v1/governance`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'X-User-ID': session.user.id,
      },
    });

    if (!backendResponse.ok) {
      const errorData = await backendResponse.json().catch(() => ({}));
      return backendError('governance', errorData.message).toResponse();
    }

    const data = await backendResponse.json();

    const response: GovernanceResponse = {
      success: true,
      data: {
        rate_limits: data.rate_limits || [],
        budgets: data.budgets || {
          llm_tokens: { used: 0, limit: 0 },
          apify_runs: { used: 0, limit: 0 },
          browser_sessions: { used: 0, limit: 0 },
        },
        circuit_breakers: data.circuit_breakers || {},
        agent_health: data.agent_health || [],
        kill_switches: data.kill_switches || {},
      },
    };

    return Response.json(response, { status: 200 });
  } catch (error) {
    console.error('[ZRAI:governance] Error:', error);
    return backendError('governance', error instanceof Error ? error.message : 'Unknown error').toResponse();
  }
}
