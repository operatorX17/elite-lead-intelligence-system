/**
 * ZRAI Lead OS - Error Handling
 * 
 * Custom error classes and utilities for ZRAI API responses.
 */

import { ZRAI_ERROR_CODES, type ZRAIErrorCode } from './constants';
import type { ZRAIError } from './types';

// ============================================================================
// Error Types
// ============================================================================

export type ZRAISurface =
  | 'discover'
  | 'enrich'
  | 'intent'
  | 'proof'
  | 'score'
  | 'outreach'
  | 'conversation'
  | 'governance'
  | 'ab-test'
  | 'run'
  | 'leads'
  | 'metrics'
  | 'import';

// ============================================================================
// ZRAI Error Class
// ============================================================================

export class ZRAIAPIError extends Error {
  code: ZRAIErrorCode;
  surface: ZRAISurface;
  statusCode: number;
  details?: Record<string, unknown>;
  retryAfter?: number;

  constructor(
    code: ZRAIErrorCode,
    surface: ZRAISurface,
    message?: string,
    details?: Record<string, unknown>,
    retryAfter?: number
  ) {
    super(message || getMessageByErrorCode(code));
    this.code = code;
    this.surface = surface;
    this.statusCode = getStatusCodeByErrorCode(code);
    this.details = details;
    this.retryAfter = retryAfter;
  }

  toResponse(): Response {
    const error: ZRAIError = {
      code: this.code,
      message: this.message,
      details: this.details,
      retry_after: this.retryAfter,
    };

    return Response.json(
      { success: false, error },
      { status: this.statusCode }
    );
  }

  toJSON(): ZRAIError {
    return {
      code: this.code,
      message: this.message,
      details: this.details,
      retry_after: this.retryAfter,
    };
  }
}

// ============================================================================
// Error Message Mapping
// ============================================================================

function getMessageByErrorCode(code: ZRAIErrorCode): string {
  const messages: Record<ZRAIErrorCode, string> = {
    [ZRAI_ERROR_CODES.AUTH_ERROR]: 'Authentication required. Please sign in to continue.',
    [ZRAI_ERROR_CODES.PERMISSION_ERROR]: 'You do not have permission to perform this action.',
    [ZRAI_ERROR_CODES.NOT_FOUND]: 'The requested resource was not found.',
    [ZRAI_ERROR_CODES.ALREADY_EXISTS]: 'A resource with this identifier already exists.',
    [ZRAI_ERROR_CODES.RATE_LIMIT]: 'Rate limit exceeded. Please try again later.',
    [ZRAI_ERROR_CODES.BUDGET_EXCEEDED]: 'Daily budget exceeded. Operations will resume tomorrow.',
    [ZRAI_ERROR_CODES.CIRCUIT_OPEN]: 'Service temporarily unavailable due to high error rate.',
    [ZRAI_ERROR_CODES.SERVICE_UNAVAILABLE]: 'The service is temporarily unavailable.',
    [ZRAI_ERROR_CODES.VALIDATION_ERROR]: 'Invalid input. Please check your request.',
    [ZRAI_ERROR_CODES.INVALID_INPUT]: 'The provided input is invalid.',
    [ZRAI_ERROR_CODES.BACKEND_ERROR]: 'An internal error occurred. Please try again.',
    [ZRAI_ERROR_CODES.TIMEOUT]: 'The operation timed out. Please try again.',
    [ZRAI_ERROR_CODES.GOVERNANCE_VIOLATION]: 'This action violates governance rules.',
    [ZRAI_ERROR_CODES.DO_NOT_CONTACT]: 'This lead is on the do-not-contact list.',
  };

  return messages[code] || 'An unexpected error occurred.';
}

// ============================================================================
// Status Code Mapping
// ============================================================================

function getStatusCodeByErrorCode(code: ZRAIErrorCode): number {
  const statusCodes: Record<ZRAIErrorCode, number> = {
    [ZRAI_ERROR_CODES.AUTH_ERROR]: 401,
    [ZRAI_ERROR_CODES.PERMISSION_ERROR]: 403,
    [ZRAI_ERROR_CODES.NOT_FOUND]: 404,
    [ZRAI_ERROR_CODES.ALREADY_EXISTS]: 409,
    [ZRAI_ERROR_CODES.RATE_LIMIT]: 429,
    [ZRAI_ERROR_CODES.BUDGET_EXCEEDED]: 402,
    [ZRAI_ERROR_CODES.CIRCUIT_OPEN]: 503,
    [ZRAI_ERROR_CODES.SERVICE_UNAVAILABLE]: 503,
    [ZRAI_ERROR_CODES.VALIDATION_ERROR]: 400,
    [ZRAI_ERROR_CODES.INVALID_INPUT]: 400,
    [ZRAI_ERROR_CODES.BACKEND_ERROR]: 500,
    [ZRAI_ERROR_CODES.TIMEOUT]: 504,
    [ZRAI_ERROR_CODES.GOVERNANCE_VIOLATION]: 403,
    [ZRAI_ERROR_CODES.DO_NOT_CONTACT]: 403,
  };

  return statusCodes[code] || 500;
}

// ============================================================================
// Error Factory Functions
// ============================================================================

export function authError(surface: ZRAISurface): ZRAIAPIError {
  return new ZRAIAPIError(ZRAI_ERROR_CODES.AUTH_ERROR, surface);
}

export function permissionError(surface: ZRAISurface, details?: Record<string, unknown>): ZRAIAPIError {
  return new ZRAIAPIError(ZRAI_ERROR_CODES.PERMISSION_ERROR, surface, undefined, details);
}

export function notFoundError(surface: ZRAISurface, resource?: string): ZRAIAPIError {
  return new ZRAIAPIError(
    ZRAI_ERROR_CODES.NOT_FOUND,
    surface,
    resource ? `${resource} not found.` : undefined
  );
}

export function validationError(surface: ZRAISurface, details: Record<string, unknown>): ZRAIAPIError {
  return new ZRAIAPIError(ZRAI_ERROR_CODES.VALIDATION_ERROR, surface, undefined, details);
}

export function rateLimitError(surface: ZRAISurface, retryAfter: number): ZRAIAPIError {
  return new ZRAIAPIError(
    ZRAI_ERROR_CODES.RATE_LIMIT,
    surface,
    `Rate limit exceeded. Try again in ${retryAfter} seconds.`,
    undefined,
    retryAfter
  );
}

export function budgetExceededError(surface: ZRAISurface, resource: string): ZRAIAPIError {
  return new ZRAIAPIError(
    ZRAI_ERROR_CODES.BUDGET_EXCEEDED,
    surface,
    `Daily budget exceeded for ${resource}.`
  );
}

export function circuitOpenError(surface: ZRAISurface, agent: string): ZRAIAPIError {
  return new ZRAIAPIError(
    ZRAI_ERROR_CODES.CIRCUIT_OPEN,
    surface,
    `${agent} is temporarily unavailable due to high error rate.`
  );
}

export function backendError(surface: ZRAISurface, cause?: string): ZRAIAPIError {
  return new ZRAIAPIError(
    ZRAI_ERROR_CODES.BACKEND_ERROR,
    surface,
    cause ? `Backend error: ${cause}` : undefined
  );
}

export function doNotContactError(surface: ZRAISurface, leadId: string): ZRAIAPIError {
  return new ZRAIAPIError(
    ZRAI_ERROR_CODES.DO_NOT_CONTACT,
    surface,
    'This lead is on the do-not-contact list and cannot be contacted.',
    { lead_id: leadId }
  );
}

// ============================================================================
// Error Handling Utilities
// ============================================================================

/**
 * Wraps an async handler with error handling.
 */
export function withErrorHandling<T>(
  surface: ZRAISurface,
  handler: () => Promise<T>
): Promise<T | Response> {
  return handler().catch((error) => {
    if (error instanceof ZRAIAPIError) {
      return error.toResponse();
    }

    console.error(`[ZRAI:${surface}] Unhandled error:`, error);
    return backendError(surface, error instanceof Error ? error.message : 'Unknown error').toResponse();
  });
}

/**
 * Creates a user-friendly error message from a ZRAIError.
 */
export function getUserFriendlyMessage(error: ZRAIError): string {
  // Don't expose internal details
  if (error.code === ZRAI_ERROR_CODES.BACKEND_ERROR) {
    return 'Something went wrong. Please try again.';
  }

  return error.message;
}

/**
 * Suggests recovery actions based on error code.
 */
export function getSuggestedRecovery(error: ZRAIError): string | null {
  switch (error.code) {
    case ZRAI_ERROR_CODES.AUTH_ERROR:
      return 'Please sign in and try again.';
    case ZRAI_ERROR_CODES.RATE_LIMIT:
      return error.retry_after
        ? `Please wait ${error.retry_after} seconds and try again.`
        : 'Please wait a moment and try again.';
    case ZRAI_ERROR_CODES.BUDGET_EXCEEDED:
      return 'Budget will reset at midnight. Try again tomorrow.';
    case ZRAI_ERROR_CODES.CIRCUIT_OPEN:
      return 'The service is recovering. Please try again in a few minutes.';
    case ZRAI_ERROR_CODES.TIMEOUT:
      return 'The operation took too long. Try with fewer items or try again later.';
    default:
      return null;
  }
}
