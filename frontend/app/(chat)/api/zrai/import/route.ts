/**
 * ZRAI Lead OS - Import Endpoint
 * 
 * POST /api/zrai/import
 * Imports leads from CSV or other sources.
 */

import { z } from 'zod';
import { auth } from '@/app/(auth)/auth';
import { importLeadsToSupabase } from '@/lib/zrai/import-bridge';
import {
  authError,
  backendError,
  validationError,
} from '@/lib/zrai/errors';
import type { CSVImportResult } from '@/lib/zrai/types';









// ============================================================================
// Request Schema
// ============================================================================

const importRequestSchema = z.object({
  leads: z.array(z.object({
    company_name: z.string().min(1),
    domain: z.string().min(1),
    niche: z.string().optional(),
    geo: z.string().optional(),
    contacts: z.array(z.object({
      name: z.string().optional(),
      email: z.string().email().optional(),
      phone: z.string().optional(),
      linkedin_url: z.string().url().optional(),
      title: z.string().optional(),
    })).optional(),
  })).min(1, 'At least one lead is required'),
  source: z.string().min(1, 'Source is required'),
});

type ImportRequest = z.infer<typeof importRequestSchema>;

// ============================================================================
// Response Types
// ============================================================================

interface ImportResponse {
  success: boolean;
  data?: CSVImportResult;
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
      return authError('import').toResponse();
    }

    // Parse and validate request
    let body: ImportRequest;
    try {
      const json = await request.json();
      body = importRequestSchema.parse(json);
    } catch (error) {
      if (error instanceof z.ZodError) {
        return validationError('import', {
          errors: error.errors.map((e) => ({
            field: e.path.join('.'),
            message: e.message,
          })),
        }).toResponse();
      }
      return validationError('import', { message: 'Invalid JSON body' }).toResponse();
    }

    const data = await importLeadsToSupabase(body.leads, body.source);

    const response: ImportResponse = {
      success: true,
      data: {
        success: data.success,
        total_rows: data.total_rows,
        imported: data.imported,
        failed: data.failed,
        errors: data.errors || [],
        leads: data.leads,
      },
    };

    return Response.json(response, { status: 200 });
  } catch (error) {
    console.error('[ZRAI:import] Error:', error);
    return backendError('import', error instanceof Error ? error.message : 'Unknown error').toResponse();
  }
}

