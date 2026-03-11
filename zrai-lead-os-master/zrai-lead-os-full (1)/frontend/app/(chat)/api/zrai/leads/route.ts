/**
 * ZRAI Lead OS - Leads Data Endpoint
 * 
 * GET /api/zrai/leads - Get paginated list of leads
 * GET /api/zrai/leads/:id - Get single lead
 */

import { z } from 'zod';
import { auth } from '@/app/(auth)/auth';
import { DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, ZRAI_BACKEND_URL } from '@/lib/zrai/constants';
import {
  authError,
  backendError,
  notFoundError,
  validationError,
} from '@/lib/zrai/errors';
import type { Lead, PaginatedResponse } from '@/lib/zrai/types';

// ============================================================================
// Query Schema
// ============================================================================

const leadsQuerySchema = z.object({
  page: z.coerce.number().min(1).optional().default(1),
  page_size: z.coerce.number().min(1).max(MAX_PAGE_SIZE).optional().default(DEFAULT_PAGE_SIZE),
  niche: z.string().optional(),
  geo: z.string().optional(),
  status: z.string().optional(),
  min_score: z.coerce.number().min(0).max(100).optional(),
  sort_by: z.string().optional().default('created_at'),
  sort_order: z.enum(['asc', 'desc']).optional().default('desc'),
});

type LeadsQuery = z.infer<typeof leadsQuerySchema>;

// ============================================================================
// Response Types
// ============================================================================

interface LeadsResponse {
  success: boolean;
  data?: PaginatedResponse<Lead>;
  error?: {
    code: string;
    message: string;
  };
}

interface LeadResponse {
  success: boolean;
  data?: Lead;
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
      return authError('leads').toResponse();
    }

    // Get lead ID from URL if present
    const url = new URL(request.url);
    const pathParts = url.pathname.split('/');
    const leadId = pathParts[pathParts.length - 1];

    // Check if this is a single lead request
    if (leadId && leadId !== 'leads' && leadId.match(/^[0-9a-f-]{36}$/i)) {
      return getSingleLead(leadId, session.user.id);
    }

    // Parse query parameters
    let query: LeadsQuery;
    try {
      const params = Object.fromEntries(url.searchParams.entries());
      query = leadsQuerySchema.parse(params);
    } catch (error) {
      if (error instanceof z.ZodError) {
        return validationError('leads', {
          errors: error.errors.map((e) => ({
            field: e.path.join('.'),
            message: e.message,
          })),
        }).toResponse();
      }
      return validationError('leads', { message: 'Invalid query parameters' }).toResponse();
    }

    // Build query string for backend
    const backendParams = new URLSearchParams();
    Object.entries(query).forEach(([key, value]) => {
      if (value !== undefined) {
        backendParams.set(key, String(value));
      }
    });

    // Call ZRAI backend
    const backendResponse = await fetch(
      `${ZRAI_BACKEND_URL}/api/v1/leads?${backendParams.toString()}`,
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
      return backendError('leads', errorData.message).toResponse();
    }

    const data = await backendResponse.json();

    const response: LeadsResponse = {
      success: true,
      data: {
        items: data.leads || data.items || [],
        total: data.total || 0,
        page: query.page,
        page_size: query.page_size,
        has_more: data.has_more || (data.total > query.page * query.page_size),
      },
    };

    return Response.json(response, { status: 200 });
  } catch (error) {
    console.error('[ZRAI:leads] Error:', error);
    return backendError('leads', error instanceof Error ? error.message : 'Unknown error').toResponse();
  }
}

// ============================================================================
// Single Lead Handler
// ============================================================================

async function getSingleLead(leadId: string, userId: string): Promise<Response> {
  try {
    const backendResponse = await fetch(`${ZRAI_BACKEND_URL}/api/v1/leads/${leadId}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'X-User-ID': userId,
      },
    });

    if (!backendResponse.ok) {
      const errorData = await backendResponse.json().catch(() => ({}));

      if (backendResponse.status === 404) {
        return notFoundError('leads', 'Lead').toResponse();
      }

      return backendError('leads', errorData.message).toResponse();
    }

    const data = await backendResponse.json();

    const response: LeadResponse = {
      success: true,
      data: data.lead || data,
    };

    return Response.json(response, { status: 200 });
  } catch (error) {
    console.error('[ZRAI:leads] Error:', error);
    return backendError('leads', error instanceof Error ? error.message : 'Unknown error').toResponse();
  }
}
