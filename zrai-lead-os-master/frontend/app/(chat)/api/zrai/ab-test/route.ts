/**
 * ZRAI Lead OS - A/B Test Endpoint
 * 
 * POST /api/zrai/ab-test - Create or manage A/B tests
 * GET /api/zrai/ab-test/:id - Get A/B test results
 */

import { z } from 'zod';
import { auth } from '@/app/(auth)/auth';
import { ZRAI_BACKEND_URL } from '@/lib/zrai/constants';
import {
  authError,
  backendError,
  notFoundError,
  validationError,
} from '@/lib/zrai/errors';
import type { ABTest } from '@/lib/zrai/types';

// ============================================================================
// Request Schemas
// ============================================================================

const createTestSchema = z.object({
  action: z.literal('create'),
  name: z.string().min(1, 'Name is required'),
  description: z.string().optional(),
  variants: z.array(z.object({
    name: z.string().min(1),
    description: z.string().optional(),
    config: z.record(z.unknown()),
  })).min(2, 'At least 2 variants required'),
  metric: z.string().min(1, 'Metric is required'),
});

const actionTestSchema = z.object({
  action: z.enum(['start', 'pause', 'conclude']),
  test_id: z.string().uuid('Invalid test ID format'),
});

const abTestRequestSchema = z.union([createTestSchema, actionTestSchema]);

type ABTestRequest = z.infer<typeof abTestRequestSchema>;

// ============================================================================
// Response Types
// ============================================================================

interface ABTestResponse {
  success: boolean;
  data?: ABTest;
  error?: {
    code: string;
    message: string;
  };
}

// ============================================================================
// Route Handlers
// ============================================================================

export async function POST(request: Request): Promise<Response> {
  try {
    // Authenticate
    const session = await auth();
    if (!session?.user) {
      return authError('ab-test').toResponse();
    }

    // Parse and validate request
    let body: ABTestRequest;
    try {
      const json = await request.json();
      body = abTestRequestSchema.parse(json);
    } catch (error) {
      if (error instanceof z.ZodError) {
        return validationError('ab-test', {
          errors: error.errors.map((e) => ({
            field: e.path.join('.'),
            message: e.message,
          })),
        }).toResponse();
      }
      return validationError('ab-test', { message: 'Invalid JSON body' }).toResponse();
    }

    // Call ZRAI backend
    const backendResponse = await fetch(`${ZRAI_BACKEND_URL}/api/v1/ab-test`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-User-ID': session.user.id,
      },
      body: JSON.stringify(body),
    });

    if (!backendResponse.ok) {
      const errorData = await backendResponse.json().catch(() => ({}));

      if (backendResponse.status === 404) {
        return notFoundError('ab-test', 'A/B Test').toResponse();
      }

      return backendError('ab-test', errorData.message).toResponse();
    }

    const data = await backendResponse.json();

    const response: ABTestResponse = {
      success: true,
      data: data.test || data,
    };

    return Response.json(response, { status: 200 });
  } catch (error) {
    console.error('[ZRAI:ab-test] Error:', error);
    return backendError('ab-test', error instanceof Error ? error.message : 'Unknown error').toResponse();
  }
}

export async function GET(request: Request): Promise<Response> {
  try {
    // Authenticate
    const session = await auth();
    if (!session?.user) {
      return authError('ab-test').toResponse();
    }

    // Get test ID from URL
    const url = new URL(request.url);
    const testId = url.pathname.split('/').pop();

    if (!testId || testId === 'ab-test') {
      // List all tests
      const backendResponse = await fetch(`${ZRAI_BACKEND_URL}/api/v1/ab-test`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'X-User-ID': session.user.id,
        },
      });

      if (!backendResponse.ok) {
        const errorData = await backendResponse.json().catch(() => ({}));
        return backendError('ab-test', errorData.message).toResponse();
      }

      const data = await backendResponse.json();
      return Response.json({ success: true, data: data.tests || [] }, { status: 200 });
    }

    // Get specific test
    const backendResponse = await fetch(`${ZRAI_BACKEND_URL}/api/v1/ab-test/${testId}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'X-User-ID': session.user.id,
      },
    });

    if (!backendResponse.ok) {
      const errorData = await backendResponse.json().catch(() => ({}));

      if (backendResponse.status === 404) {
        return notFoundError('ab-test', 'A/B Test').toResponse();
      }

      return backendError('ab-test', errorData.message).toResponse();
    }

    const data = await backendResponse.json();

    const response: ABTestResponse = {
      success: true,
      data: data.test || data,
    };

    return Response.json(response, { status: 200 });
  } catch (error) {
    console.error('[ZRAI:ab-test] Error:', error);
    return backendError('ab-test', error instanceof Error ? error.message : 'Unknown error').toResponse();
  }
}
