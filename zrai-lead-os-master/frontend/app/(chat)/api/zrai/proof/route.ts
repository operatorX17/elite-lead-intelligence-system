/**
 * ZRAI Lead OS - Proof Generation Endpoint
 * 
 * POST /api/zrai/proof
 * Generates proof artifacts (screenshots, recordings) via the ZRAI Audit Agent.
 */

import { z } from 'zod';
import { auth } from '@/app/(auth)/auth';
import { ZRAI_BACKEND_URL } from '@/lib/zrai/constants';
import {
  authError,
  backendError,
  notFoundError,
  validationError,
  ZRAIAPIError,
} from '@/lib/zrai/errors';
import type { ProofArtifact } from '@/lib/zrai/types';

// ============================================================================
// Request Schema
// ============================================================================

const proofRequestSchema = z.object({
  lead_id: z.string().uuid('Invalid lead ID format'),
  proof_type: z.enum(['screenshot', 'recording', 'extracted_data']).default('screenshot'),
});

type ProofRequest = z.infer<typeof proofRequestSchema>;

// ============================================================================
// Response Types
// ============================================================================

interface ProofResponse {
  success: boolean;
  data?: {
    proof: ProofArtifact;
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
      return authError('proof').toResponse();
    }

    // Parse and validate request
    let body: ProofRequest;
    try {
      const json = await request.json();
      body = proofRequestSchema.parse(json);
    } catch (error) {
      if (error instanceof z.ZodError) {
        return validationError('proof', {
          errors: error.errors.map((e) => ({
            field: e.path.join('.'),
            message: e.message,
          })),
        }).toResponse();
      }
      return validationError('proof', { message: 'Invalid JSON body' }).toResponse();
    }

    // Call ZRAI backend (Steel.dev via Audit Agent)
    const backendResponse = await fetch(`${ZRAI_BACKEND_URL}/api/v1/proof`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-User-ID': session.user.id,
      },
      body: JSON.stringify({
        lead_id: body.lead_id,
        proof_type: body.proof_type,
      }),
    });

    if (!backendResponse.ok) {
      const errorData = await backendResponse.json().catch(() => ({}));

      if (backendResponse.status === 404) {
        return notFoundError('proof', 'Lead').toResponse();
      }

      if (backendResponse.status === 429) {
        return new ZRAIAPIError(
          'rate_limit',
          'proof',
          errorData.message || 'Rate limit exceeded',
          undefined,
          errorData.retry_after
        ).toResponse();
      }

      if (backendResponse.status === 402) {
        return new ZRAIAPIError(
          'budget_exceeded',
          'proof',
          errorData.message || 'Budget exceeded for browser sessions'
        ).toResponse();
      }

      if (backendResponse.status === 503) {
        return new ZRAIAPIError(
          'circuit_open',
          'proof',
          errorData.message || 'Audit agent is temporarily unavailable'
        ).toResponse();
      }

      // Handle specific proof generation failures
      if (errorData.code === 'site_blocked') {
        return new ZRAIAPIError(
          'backend_error',
          'proof',
          'Unable to access the website. It may be blocking automated access.'
        ).toResponse();
      }

      if (errorData.code === 'timeout') {
        return new ZRAIAPIError(
          'timeout',
          'proof',
          'Screenshot generation timed out. The website may be slow to load.'
        ).toResponse();
      }

      return backendError('proof', errorData.message).toResponse();
    }

    const data = await backendResponse.json();

    const response: ProofResponse = {
      success: true,
      data: {
        proof: data.proof,
      },
    };

    return Response.json(response, { status: 200 });
  } catch (error) {
    console.error('[ZRAI:proof] Error:', error);
    return backendError('proof', error instanceof Error ? error.message : 'Unknown error').toResponse();
  }
}
